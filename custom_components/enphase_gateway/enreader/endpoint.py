"""Enphase gateway endpoint module."""

import time
import json

from collections import UserDict


class GatewayEndpoint:
    """Class representing a Gateway endpoint."""

    def __init__(
            self,
            path: str,
            cache_for: int = 0,
    ) -> None:
        """Initialize instance.

        Parameters
        ----------
        endpoint_path : str
            Relative path of the endpoint.
        cache : int, optional
            Number of seconds the endpoint is cached for. The default is 0.
        fetch : bool, optional
            Fetch the endpoint if `True`. The default is True.

        """
        self.path = path
        self.data = None
        self.cache_for = cache_for
        self._timestamp = 0

    def __repr__(self) -> str:
        """Return a printable representation."""
        return self.path

    @property
    def cache_expired(self) -> bool:
        """Return if the cache is expired."""
        if (self._timestamp + self._cache_for) <= time.time():
            return True

        return False

    async def update(self, request, force: bool = False) -> None:
        """Fetch new data from the endpoint."""
        if not self.cache_expired and not force:
            return

        self.data = await self.fetch(request)
        self._timestamp = time.time()

    async def fetch(self, request):
        """Fetch the endpoint and return the decoded data."""
        response = await request(self.path)

        return self._decode_response(response)

    def _decode_response(self, response):
        """Decode the response content."""
        content_type = response.headers.get("content-type", "application/json")

        if content_type == "application/json":
            return json.loads(response.content)
        elif content_type in ("text/xml", "application/xml"):
            return response.content
        else:
            response.text





class GatewayEndpointBackup:
    """Class representing a Gateway endpoint."""

    def __init__(
            self,
            endpoint_path: str,
            cache: int = 0,
            fetch: bool = True
    ) -> None:
        """Initialize instance.

        Parameters
        ----------
        endpoint_path : str
            Relative path of the endpoint.
        cache : int, optional
            Number of seconds the endpoint is cached for. The default is 0.
        fetch : bool, optional
            Fetch the endpoint if `True`. The default is True.

        """
        self.path = endpoint_path
        self.cache = cache
        self.fetch = fetch
        self._last_fetch = None

    def __repr__(self) -> str:
        """Return a printable representation."""
        return self.path

    @property
    def update_required(self) -> bool:
        """Determine if an update is required for this endpoint."""
        if self.fetch is False:
            return False
        elif not self._last_fetch:
            return True
        elif (self._last_fetch + self.cache) <= time.time():
            return True

        return False

    def get_url(self, protocol: str, host: str) -> str:
        """Return the url for the endpoint.

        Parameters
        ----------
        protocol : {'http', 'https'}
            HTTP protocol version.
        host : str
            Hostname.

        Returns
        -------
        str
            Url for the endpoint.

        """
        return f"{protocol}://{host}/{self.path}"

    def success(self, timestamp: float = None) -> None:
        """Update the last_fetch timestamp."""
        if not timestamp:
            timestamp = time.time()
        self._last_fetch = timestamp



