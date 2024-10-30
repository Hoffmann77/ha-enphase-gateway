"""Read parameters from an Enphase(R) gateway on your local network."""

import logging
from collections.abc import Iterable

import httpx
from awesomeversion import AwesomeVersion
from envoy_utils.envoy_utils import EnvoyUtils

from .http import async_get, async_request
from .endpoint import GatewayEndpoint
from .utils import is_ipv6_address
from .gateway import EnphaseGateway, EnvoyLegacy, Envoy, EnvoyS, EnvoySMetered
from .const import LEGACY_ENVOY_VERSION
from .gateway_info import GatewayInfo
from .auth import LegacyAuth, EnphaseTokenAuth
from .exceptions import GatewayAuthenticationRequired, GatewaySetupError
from .models import Info


_LOGGER = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "Accept": "application/json",
}


class GatewayReader:
    """Retrieve data from an Enphase gateway.

    Parameters
    ----------
    host : str
        Hostname of the Gateway.
    async_client : httpx.AsyncClient, optional
        Async httpx client. A client will be created if no client is provided.

    Attributes
    ----------
    host : str
        Hostname of the Gateway.
    auth : {LegacyAuth, EnphaseTokenAuth}
        Gateway authentication class.
    gateway : Gateway class.
        Gateway class to access gateway data.

    """

    def __init__(
            self,
            host: str,
            async_client: httpx.AsyncClient | None = None,
            # For the future:
            # client_verify_ssl: httpx.AsyncClient,
            # client_no_verify_ssl: httpx.AsyncClient,
    ) -> None:
        """Initialize instance of Enreader.

        Parameters
        ----------
        host : str
            Host.
        async_client : httpx.AsyncClient | None, optional
            DESCRIPTION. The default is None.
         : TYPE
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
        self.host = host.lower()
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"

        self.auth = None
        self.gateway = None
        self._async_client = async_client or self._get_async_client()
        # For the future:
        # self._client_verify_ssl = client_verify_ssl
        # self._client_no_verify_ssl = client_no_verify_ssl
        self._info = GatewayInfo(self.host, self._async_client)

    # Required for endpoint tests
    def _get_async_client(self) -> httpx.AsyncClient:
        """Return default httpx client."""
        return httpx.AsyncClient(
            verify=False,
            timeout=10
        )

    @property
    def name(self) -> str | None:
        """Return the verbose name."""
        if self.gateway:
            return self.gateway.VERBOSE_NAME

        return "Enphase Gateway"

    @property
    def serial_number(self) -> str | None:
        """Return the serial number."""
        return self._info.serial_number

    @property
    def part_number(self) -> str | None:
        """Return the part number."""
        return self._info.part_number

    @property
    def firmware_version(self) -> AwesomeVersion:
        """Return the firmware version."""
        return self._info.firmware_version

    async def authenticate(
        self,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> None:
        _LOGGER.debug("Starting authentication process...")
        info = await self._get_info()

        assert info.serial_number is not None

        self.auth = await self._authenticate(info, username, password, token)

        # Detect the correct gateway class.
        gateway = await self._detect_gateway(info)
        self.gateway = await self._probe_gateway(gateway)

        _LOGGER.debug(
            "Authentication finished: "
            + f"Authentication class: {self.auth.__class__.__name__}, "
            + f"Gateway class: {self.gateway.__class__.__name__}, "
        )

    async def _authenticate(
        self,
        info: Info,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> None:
        """Authenticate to the Enphase gateway.

        Parse the info.xml endpoint to determine the required auth class.

        Parameters
        ----------
        username : str, optional
            Username.
        password : str, optional
            Password.
        token : str, optional
            Enphase JWT token.

        Raises
        ------
        GatewayAuthenticationRequired
            DESCRIPTION.

        """
        _LOGGER.debug("Starting authentication process...")
        info = await self._get_info()

        assert info.serial_number is not None

        _LOGGER.debug(
            "Detecting authenticating method based on info: "
            + f"part_number: {info.part_number}, "
            + f"firmware_version: {info.firmware_version}, "
            + f"imeter: {info.imeter}, "
            + f"web_tokens: {info.web_tokens}, "
        )

        if info.web_tokens:
            # Firmware using token based authentication
            if token or (username and password):
                auth = EnphaseTokenAuth(
                    self.host,
                    enlighten_username=username,
                    enlighten_password=password,
                    serial_number=self.serial_number,
                    token_raw=token,
                )
        else:
            # Firmware using old installer/envoy authentication
            if not username or username == "installer":
                username = "installer"
                password = EnvoyUtils.get_password(
                    info.serial_number, username
                )
            elif username == "envoy" and not password:
                # The default password for the envoy user
                # is the last 6 digits of the serial number.
                password = info.serial_number[:6]

            if username and password:
                auth = LegacyAuth(self.host, username, password)

        if not auth:
            _LOGGER.error(
                "You must provide a valid username/password or token "
                + "to authenticate to the Enphase gateway."
            )
            raise GatewayAuthenticationRequired(
                "Could not setup authentication method."
            )

        # Update the authentication method to check if configured correctly.
        await auth.setup(self._async_client)

        return auth



    async def update(self) -> None:
        """Update the gateway's data.

        Fetch new data from all required endpoints and update the gateway.

        """
        await self.gateway.update(self.request)






    async def request(self, endpoint: str) -> httpx.Response:
        """Make a request to the Envoy.

        Request retries on bad JSON responses which the Envoy sometimes returns.
        """
        return await self._request(endpoint)

    async def _request(self, endpoint: str, handle_401: bool = True):
        """Send a HTTP request."""
        if self.auth is None:
            raise GatewayAuthenticationRequired(
                "You must authenticate to the gateway before making requests."
            )

        headers = self.auth.headers or {}
        try:
            response = await async_request(
                "GET",
                f"{self.auth.protocol}://{self.host}{endpoint}",
                self._async_client,
                headers={**DEFAULT_HEADERS, **headers},
                cookies=self.auth.cookies,
                auth=self.auth.auth,
            )
        except httpx.HTTPStatusError as err:
            if response.status_code == 401 and handle_401:
                self.auth.resolve_401(self._async_client)
                return await self._request(endpoint, handle_401=False)
            else:
                raise err
        else:
            return response

    async def _async_get(self, url: str, **kwargs):
        """Send a simple HTTP get request."""

        return await async_get(url, self._async_client, **kwargs)

















    async def _get_info(self) -> Info:
        """Return the Info model."""
        try:
            response = await self._async_get(f"https://{self.host}/info")
        except (httpx.ConnectError, httpx.TimeoutException):
            # Firmware < 7.0.0 does not support HTTPS so we need to try HTTP.
            # Worse sometimes http will redirect to https://localhost.
            response = await self._async_get(f"http://{self.host}/info")

        return Info.from_response(response)

    async def _detect_gateway(self, info: Info) -> EnphaseGateway:
        """Detect the Enphase gateway model.

        Detect the gateway model based on info.xml parmeters.

        """
        _LOGGER.debug("Detecting gateway model...")

        if info.firmware_version < LEGACY_ENVOY_VERSION:
            gateway = EnvoyLegacy()
        elif info.imeter is not None:
            # info.xml has the `imeter` tag.
            if info.imeter:
                gateway = EnvoySMetered()
            else:
                gateway = EnvoyS()
        else:
            gateway = Envoy()

        _LOGGER.debug(
            f"Detected base gateway: {gateway.__class__.__name__}"
        )

        return gateway

        # _LOGGER.debug("Running gateway probes...")

        # subclass = await self.gateway.probe(self.request)
        # if subclass:
        #     self.gateway = subclass

        # _LOGGER.debug(f"Gateway model: {self.gateway.__class__.__name__}")

    async def _probe_gateway(self, gateway: EnphaseGateway) -> EnphaseGateway:

        _LOGGER.debug("Running gateway probes...")

        subclass = await gateway.probe(self.request)
        if subclass:

            return subclass

        return gateway

