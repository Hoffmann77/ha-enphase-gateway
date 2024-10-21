"""Enphase Gateway authentication module."""

import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod, abstractproperty

import jwt
import httpx
import orjson
from bs4 import BeautifulSoup

from .http import async_get, async_post
from .exceptions import (
    EnlightenAuthenticationError,
    EnlightenCommunicationError,
    GatewayAuthenticationError,
    GatewayCommunicationError,
    InvalidTokenError,
    # TokenAuthConfigError,
    # TokenRetrievalError,
)


_LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


class GatewayAuth(ABC):
    """Abstract base class for gateway authentication."""

    def __init__(self) -> None:
        """Initialize GatewayAuth."""
        pass

    @abstractproperty
    def protocol(self) -> str:
        """Return the http protocol."""

    @abstractproperty
    def auth(self) -> httpx.Auth | None:
        """Return the httpx auth object."""

    @abstractproperty
    def headers(self) -> dict[str, str]:
        """Return the auth headers."""

    @abstractproperty
    def cookies(self) -> dict[str, str]:
        """Return the cookies."""

    @abstractproperty
    def is_stale(self) -> bool:
        """Return if a refresh of authentication medthod is necessary."""

    @abstractmethod
    async def setup(self, client: httpx.AsyncClient) -> None:
        """Set up the authentication method."""

    @abstractmethod
    async def refresh(self, client: httpx.AsyncClient) -> None:
        """Refresh the authentication method."""

    @abstractmethod
    async def resolve_401(self, async_client: httpx.AsyncClient) -> None:
        """Handle a HTTP 401 Unauthorized response."""


class LegacyAuth(GatewayAuth):
    """Class for legacy authentication using username and password."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self._host = host
        self._username = username
        self._password = password

    @property
    def protocol(self) -> str:
        """Return http protocol."""
        return "http"

    @property
    def auth(self) -> httpx.DigestAuth:
        """Return httpx authentication."""
        if not self._username or not self._password:
            return None

        return httpx.DigestAuth(self._username, self._password)

    @property
    def headers(self) -> dict[str, str] | None:
        """Return the headers for legacy authentication."""
        return None

    @property
    def cookies(self) -> dict[str, str] | None:
        """Return the cookies for legacy authentication."""
        return None

    @property
    def is_stale(self) -> bool:
        """Return if a refresh of the authentication medthod is necessary."""
        return False

    async def setup(self, client: httpx.AsyncClient) -> None:
        """Set up the authentication method."""
        pass

    async def refresh(self, client: httpx.AsyncClient) -> None:
        """Refresh the authentication method."""
        pass

    async def resolve_401(self, async_client):
        """Resolve a 401 Unauthorized response."""
        pass


class EnphaseTokenAuth(GatewayAuth):
    """Class used for Enphase token authentication.

    Parameters
    ----------
    host : str
        Gateway host ip-adress.
    enlighten_username : str, optional
        Enlighten login username.
    enlighten_password : str, optional
        Enlighten login password.
    gateway_serial_num : str, optional
        Gateway serial number.
    token_raw : str, optional
        Enphase token.
    cache_token : bool, default=False
        Cache the token.
    cache_filepath : str, default="token.json"
        Cache filepath.
    auto_renewal : bool, default=True,
        Auto renewal of the token. Defaults to False if the arguments
        'enlighten_username', 'enlighten_password' and 'gateway_serial_num'
        are not provided.
    stale_token_threshold : datetime.timedelta, default=timedelta(days=30)
        Timedelta describing the stale token treshold.

    Raises
    ------
    TokenAuthConfigError
        If token authentication is not set up correcty.
    TokenRetrievalError
        If a token could not be retrieved from the Enlighten cloud.
    InvalidTokenError
        If a token is not valid.
    GatewayAuthenticationError
        If gateway authentication could not be set up.
    EnlightenAuthenticationError
        If Enlighten cloud credentials are not valid.

    """

    LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
    TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"

    def __init__(
            self,
            host: str,
            enlighten_username: str,
            enlighten_password: str,
            serial_number: str,
            token_raw: str | None = None,
    ) -> None:
        """Initialize the token based authentication.

        Parameters
        ----------
        host : str
            Hostname.
        enlighten_username : str
            Username for the Enlighten platform.
        enlighten_password : str
            Password for the Enlighten platform.
        serial_number : str
            Serial number of the Enphase gateway.
        token_raw : str, optional
            Enphase JWT token.

        Raises
        ------
        TokenAuthConfigError
            DESCRIPTION.

        """
        self._host = host
        self._enlighten_username = enlighten_username
        self._enlighten_password = enlighten_password
        self._serial_number = serial_number
        self._token = token_raw
        self._token_exp_date = None
        self._cookies = None

    @property
    def protocol(self) -> str:
        """Return the HTTP protocol version."""
        return "https"

    @property
    def auth(self) -> httpx.Auth | None:
        """Return the httpx auth object."""
        # Token authentication uses an Authorization header
        # instead of a httpx Auth object.
        return None

    @property
    def headers(self) -> dict[str, str] | None:
        """Return the headers for token authentication."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}

        return None

    @property
    def cookies(self) -> dict[str, str] | None:
        """Return the cookies for token authentication."""
        return self._cookies

    @property
    def token(self) -> str | None:
        """Return the Enphase token."""
        return self._token

    @property
    def is_stale(self) -> bool:
        """Return if the auth object is stale."""
        # TODO: handle self._token_exp_date = None
        exp_time = self._token_exp_date - timedelta(days=30)
        if datetime.now(tz=timezone.utc) > exp_time:
            return True

        return False

    async def setup(self, async_client: httpx.AsyncClient) -> None:
        """Set up the token based authentication.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client.

        Raises
        ------
        GatewayAuthenticationError
            Raised if the authentication failed.

        """
        if not self._token:
            self._refresh_token()

        if not self._token:
            raise GatewayAuthenticationError(
                "Could not obtain a token for token authentication"
            )

        self._refresh_cookies(async_client)

    async def refresh(self, async_client: httpx.AsyncClient) -> None:
        """Refresh the token based authentication.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client.

        """
        self._refresh_token(async_client)
        self._refresh_cookies(async_client)

    async def resolve_401(self, async_client: httpx.AsyncClient) -> bool:
        """Resolve 401 Unauthorized response.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client.

        Raises
        ------
        GatewayCommunicationError
            DESCRIPTION.

        """
        try:
            self._refresh_cookies(async_client)
        except httpx.TransportError as err:
            raise GatewayCommunicationError(
                "Error trying to refresh token cookies: {err}",
                request=err.request,
            ) from err
        except InvalidTokenError:
            self._token = None
            self._cookies = None
            self.update(async_client)

    async def _refresh_token(self, async_client: httpx.AsyncClient) -> None:
        """Refresh the Enphase token.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client that does not verify ssl.

        """
        _LOGGER.debug("Refreshing the Enphase token")

        token = await self._retrieve_token(async_client)
        if token:
            # Decode the token to verify the integrity
            token_payload = self._decode_token(token)

            # Set the new token, expiration date and reset the cookies
            self._token = token
            self._cookies = None
            self._token_exp_date = datetime.fromtimestamp(
                token_payload["exp"], tz=timezone.utc
            )

            _LOGGER.debug(f"New token valid until: {self._token_exp_date}")

    async def _refresh_cookies(self, async_client: httpx.AsyncClient) -> None:
        """Try to refresh the cookies.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client that does not verify ssl.

        """
        _LOGGER.debug("Refreshing the cookies")

        cookies = await self._check_jwt(async_client, self._token)
        if cookies is not None:
            self._cookies = cookies

    def _decode_token(self, token: str) -> dict:
        """Decode the given JWT token."""
        try:
            jwt_payload = jwt.decode(
                token,
                algorithms=["ES256"],
                options={"verify_signature": False},
            )
        except jwt.exceptions.InvalidTokenError as err:
            _LOGGER.debug(f"Error decoding JWT token: {token[:6]}, {err}")
            raise err
        else:
            return jwt_payload

    async def _retrieve_token(self, async_client: httpx.AsyncClient) -> str:
        """Retrieve a new Enphase JWT token from Enlighten.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client that does verify ssl.

        Returns
        -------
        str
            Enphase JWT token.

        """
        _LOGGER.debug("Retrieving a new token from Enlighten.")

        # Retrieve the session id from Enlighten.
        resp = await self._async_post_enlighten(
            async_client,
            self.LOGIN_URL,
            data={
                'user[email]': self._enlighten_username,
                'user[password]': self._enlighten_password
            }
        )
        response_data = orjson.loads(resp.text)
        self._is_consumer = response_data["is_consumer"]
        self._manager_token = response_data["manager_token"]

        # Retrieve the actual token from Enlighten using the session id.
        resp = await self._async_post_enlighten(
            async_client,
            self.TOKEN_URL,
            json={
                'session_id': response_data['session_id'],
                'serial_num': self._gateway_serial_num,
                'username': self._enlighten_username
            }
        )

        return resp.text

    async def _async_post_enlighten(
            self,
            async_client: httpx.AsyncClient,
            url: str,
            **kwargs,
    ) -> httpx.Response:
        """Send a HTTP POST request to Enlighten.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client.
        url : str
            Target url.
        **kwargs : dict, optional
            Extra arguments to httpx.

        Raises
        ------
        EnlightenCommunicationError
            Raised for httpx transport Errors.
        EnlightenAuthenticationError
            Raised if the Enlighten credentials are invalid.

        Returns
        -------
        resp : httpx.Response
            HTTP response.

        """
        try:
            resp = await async_post(async_client, url, **kwargs)
        except httpx.TransportError as err:
            raise EnlightenCommunicationError(
                "Error communicating with the Enlighten platform",
                request=err.request,
            ) from err
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 401:
                raise EnlightenAuthenticationError(
                    "Invalid Enlighten credentials",
                    request=err.request,
                    response=err.response,
                ) from err
        else:
            return resp

    async def _check_token(
            self,
            async_client: httpx.AsyncClient,
            token: str,
    ) -> str | None:
        """Check if the Enphase JWT token is valid.

        Call the auth/check_jwt endpoint to validate the token.
        The endpoint responds:
        - 200:
            Token is in the gateway's token db. Returns 'Valid token.'
            html response and cookie 'sessionId' if the token is valid.
        - 401:
            Token is not in the gateway's token db.

        Parameters
        ----------
        async_client : httpx.AsyncClient
            Async httpx client.
        token : str
            Enphase JWT token.

        Raises
        ------
        InvalidTokenError
            Raised if the provided token is not valid.
        GatewayCommunicationError
            Raised for httpx transport errors.

        Returns
        -------
        str or None
            Return the cookies if the token is valid.

        """
        _LOGGER.debug(
            "Validating the token by using the 'auth/check_jwt' endpoint."
        )

        if not token:
            raise InvalidTokenError(
                f"The provided token is empty: '{token[:9]}...'"
            )

        try:
            resp = await async_get(
                async_client,
                f"https://{self._host}/auth/check_jwt",
                headers={"Authorization": f"Bearer {token}"},
                retries=1,
            )
        except httpx.HTTPStatusError as err:
            if resp.status_code == 401:
                raise InvalidTokenError(
                    f"The provided token is not valid: '{token[:9]}...'"
                ) from err
        except httpx.TransportError as err:
            raise GatewayCommunicationError(
                "Error trying to validate token: {err}",
                request=err.request,
            ) from err
        else:
            soup = BeautifulSoup(resp.text, features="html.parser")
            validity = soup.find("h2").contents[0]
            if validity == "Valid token.":
                _LOGGER.debug(f"Valid token: '{token[:9]}...'")
                return resp.cookies
            else:
                _LOGGER.debug(f"Invalid token: '{token[:9]}...'")

                raise InvalidTokenError(f"Invalid token: '{token[:9]}...'")
