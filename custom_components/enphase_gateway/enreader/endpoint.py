"""Enphase gateway endpoint module."""

import time
import json


class GatewayEndpoint:
    """Class representing an endpoint of the Enphase gateway."""

    def __init__(
            self,
            path: str,
            cache_for: int = 0,
    ) -> None:
        """Initialize instance.

        Parameters
        ----------
        path : str
            URL path of the endpoint.
        cache_for : int, optional
            Number of seconds the endpoint is cached for. The default is 0.

        """
        self.path = path
        self.data = None
        self.cache_for = cache_for
        self._timestamp = 0

    def __repr__(self) -> str:
        """Return a printable representation."""
        return f"Endpoint('{self.path}')"

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
