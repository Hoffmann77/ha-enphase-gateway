"""Enphase gateway endpoint module."""

import time
import json
import logging


_LOGGER = logging.getLogger(__name__)


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
        self.cache_for = cache_for
        self._timestamp = 0

    def __repr__(self) -> str:
        """Return a printable representation."""
        return f"Endpoint('{self.path}')"

    @property
    def needs_update(self) -> bool:
        """Return if the cache is expired."""
        if (self._timestamp + self.cache_for) < time.time():
            return True

        return False

    async def fetch(self, request):
        """Fetch the endpoint and return the decoded data."""
        response = await request(self.path)
        decoded = self._decode_response(response)
        self._timestamp = time.time()

        return decoded

    def _decode_response(self, response):
        """Decode the response content."""
        content_type = response.headers.get("content-type", "application/json")

        if "application/json" in content_type:
            return json.loads(response.content)
        elif content_type in ("text/xml", "application/xml"):
            return response.content
        else:
            return response.text
