"""Async http methods."""

import asyncio
import logging

import httpx


_LOGGER = logging.getLogger(__name__)


async def async_get(
    url: str,
    client: httpx.AsyncClient,
    attempts: int = 2,
    **kwargs,
) -> httpx.Response:
    """Send a HTTP GET request using the httpx client.

    Parameters
    ----------
    url : str
        URL.
    client : httpx.AsyncClient
        Instance of httpx.AsyncClient.
    attempts : int, optional
        Number of attempts to send the request if TransportErrors occur.
        The default is 2.
    **kwargs : dict
        Optional keyword arguments for httpx.AsyncClient.request.

    Returns
    -------
    response : httpx.Response
        The response from the server.

    """
    return await async_request(
        "GET", url, client, attempts=attempts, **kwargs
    )


async def async_post(
    url: str,
    client: httpx.AsyncClient,
    attempts: int = 2,
    **kwargs,
) -> httpx.Response:
    """Send a HTTP POST request using the httpx client.

    Parameters
    ----------
    url : str
        URL.
    client : httpx.AsyncClient
        Instance of httpx.AsyncClient.
    attempts : int, optional
        Number of attempts to send the request if TransportErrors occur.
        The default is 2.
    **kwargs : dict
        Optional keyword arguments to httpx.AsyncClient.request.

    Returns
    -------
    response : httpx.Response
        The response from the server.

    """
    return await async_request(
        "POST", url, client, attempts=attempts, **kwargs
    )


async def async_request(
    method: str,
    url: str,
    client: httpx.AsyncClient,
    attempts: int = 2,
    **kwargs,
) -> httpx.Response:
    """Send a HTTP request, retrying on transport errors.

    Retries up to `attempts` times when a `httpx.TransportError` occurs.
    The last transport error is re-raised once all attempts are exhausted.
    """
    last_error: httpx.TransportError | None = None
    for attempt in range(attempts):
        _LOGGER.debug(
            f"Attempt {attempt + 1} sending '{method}' request to '{url}'"
        )
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.TransportError as err:
            last_error = err
            if attempt < attempts - 1:
                await asyncio.sleep((attempt + 1) * 0.1)
                continue
            raise
        else:
            return response

    # Unreachable: the loop either returns or re-raises. Guard for safety.
    raise last_error
