"""Enphase gateway endpoint module."""

import time

from collections import UserDict


class GatewayEndpoint:
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


class EndpointCollection:
    """Custom dict for GatewayEndpoints."""

    def __init__(self) -> None:
        """Initialize instance."""
        self._endpoints = {}

    @property
    def values(self) -> list[str]:
        """Return the endpoints."""
        return self._endpoints.values()

    def add(self, new_endpoint: GatewayEndpoint) -> None:
        """Add an endpoint.

        Duplicated endpoints are ignored. Updates the caching interval
        if the new one shorter than the existing one.

        """
        _endpoint = self._endpoints.get(new_endpoint.path)

        if _endpoint is None:
            self._endpoints[new_endpoint.path] = new_endpoint

        elif new_endpoint.cache < _endpoint.cache:
            _endpoint.cache = new_endpoint.cache
