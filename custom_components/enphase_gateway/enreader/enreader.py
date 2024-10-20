"""Read parameters from an Enphase(R) gateway on your local network."""

import logging
from collections.abc import Iterable

import httpx
from awesomeversion import AwesomeVersion
from envoy_utils.envoy_utils import EnvoyUtils

from .http import async_get
from .endpoint import GatewayEndpoint
from .utils import is_ipv6_address
from .gateway import EnvoyLegacy, Envoy, EnvoyS, EnvoySMetered
from .const import LEGACY_ENVOY_VERSION
from .gateway_info import GatewayInfo
from .auth import LegacyAuth, EnphaseTokenAuth
from .exceptions import GatewayAuthenticationRequired, GatewaySetupError
from .models import Info


_LOGGER = logging.getLogger(__name__)


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
        info = await self._get_info()

        assert info.serial_number is not None

        if info.web_tokens:
            # Firmware using token based authentication
            if token or (username and password):
                self.auth = EnphaseTokenAuth(
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
                self.auth = LegacyAuth(self.host, username, password)

        if not self.auth:
            _LOGGER.error(
                "You must provide a valid username/password or token "
                + "to authenticate to the Enphase gateway."
            )
            raise GatewayAuthenticationRequired(
                "Could not setup authentication method."
            )

        # Update the authentication method to check if configured correctly.
        await self.auth.setup(self._async_client)

        # Detect the correct gateway class.
        await self._detect_model(info)

        _LOGGER.debug(
            "Gateway info: "
            + f"part_number: {self._info.part_number}, "
            + f"firmware_version: {self._info.firmware_version}, "
            + f"imeter: {self._info.imeter}, "
            + f"web_tokens: {self._info.web_tokens}"
            + f"Gateway class: {self.gateway.__class__.__name__}"
            + f"Authentication class: {self.auth.__class__.__name__}"
        )

    async def update(self) -> None:
        """Update the gateway's data.

        Fetch new data from all required endpoints and update the gateway.

        """
        required_endpoints = self.gateway.required_endpoints

        if self.gateway.initial_update_finished is False:
            self.update_endpoints(required_endpoints, force_update=True)
            self.gateway.initial_update_finished = True

        else:
            self.update_endpoints(required_endpoints)

    async def update_endpoints(
        self,
        endpoints: [GatewayEndpoint],
        force_update: bool = False,
    ) -> None:
        """Update the given endpoints.

        Parameters
        ----------
        endpoints : [GatewayEndpoint]
            List of GatewayEndpoints.
        force_update : bool, optional
            Force an update. The default is False.

        """
        _LOGGER.debug(f"Updating endpoints: {endpoints}")

        for endpoint in endpoints:
            print("endpoint: {endpoint} update required {endpoint.update_required}")
            if not endpoint.update_required and not force_update:
                continue

            url = endpoint.get_url(self.auth.protocol, self.host)
            response = await self._async_get(
                url, handle_401=True, follow_redirects=False)

            endpoint.success()

            self.gateway.set_endpoint_data(endpoint, response)

    async def _get_info(self) -> Info:
        """Return the Info model."""
        try:
            response = await self._async_get(f"https://{self.host}/info")
        except (httpx.ConnectError, httpx.TimeoutException):
            # Firmware < 7.0.0 does not support HTTPS so we need to try HTTP.
            # Worse sometimes http will redirect to https://localhost.
            response = await self._request(f"http://{self.host}/info")

        return Info.from_response(response)

    async def _detect_model(self, info: Info) -> None:
        """Detect the Enphase gateway model.

        Detect the gateway model based on info.xml parmeters.

        """
        if info.firmware_version < LEGACY_ENVOY_VERSION:
            self.gateway = EnvoyLegacy()
        elif info.imeter is not None:
            # info.xml has the `imeter` tag.
            if info.imeter:
                self.gateway = EnvoySMetered()
            else:
                self.gateway = EnvoyS()
        else:
            self.gateway = Envoy()

        self.update_endpoints(
            self.gateway.probing_endpoints, force_update=True
        )
        self.gateway.run_probes()
        if subclass := self.gateway.get_subclass():
            self.gateway = subclass
    
    # async def _request(
    #     self,
    #     url: str,
    #     handle_401: bool = False,
    #     **kwargs
    # ) -> httpx.Response:
    #     """Send a request to the Enphase gateway."""
    
    
    
    
    # for attempt in range(1, retries+2):
    #     _base_msg = f"HTTP GET Attempt #{attempt}: {url}"
    #     try:
    #         resp = await async_client.get(url, **kwargs)
    #         if raise_for_status:
    #             resp.raise_for_status()
    #     except httpx.TransportError as err:
    #         if attempt >= retries+1:
    #             _LOGGER.debug(f"{_base_msg}: Transport Error: {err}")
    #             raise err
    #         else:
    #             await asyncio.sleep(attempt * 0.10)
    #             continue
    #     else:
    #         _LOGGER.debug(
    #             f"{_base_msg}: Response: {resp}: length: {len(resp.text)}"
    #         )
    #         return resp
    
    
    async def _async_get(self, url: str, handle_401: bool = False, **kwargs):
        """Make a HTTP GET request to the gateway."""
        # TODO: How to handle async get if self.auth is None.
        # This is the case when getting the /info endpoint.
        if self.auth:
            headers, cookies = self.auth.headers, self.auth.cookies
            auth = self.auth.auth
        else:
            headers = cookies = auth = None

        try:
            resp = await async_get(
                self._async_client,
                url,
                headers=headers,
                cookies=cookies,
                auth=auth,
                **kwargs
            )
        except httpx.HTTPStatusError as err:
            _LOGGER.debug(
                f"Gateway returned status code: {err.response.status_code}"
            )
            if err.response.status_code == 401 and handle_401:
                _LOGGER.debug("Trying to resolve 401 error")
                self.auth.resolve_401(self._async_client)
                return await self._async_get(
                    url,
                    handle_401=False,
                    **kwargs
                )
            else:
                raise err

        else:
            return resp
