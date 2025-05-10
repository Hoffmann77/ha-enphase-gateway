"""Async http methods."""

import time
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

    # if debug := _LOGGER.isEnabledFor(logging.DEBUG):
    #     request_start = time.monotinic()

    for attempt in range(attempts):
        _LOGGER.debug(
            f"Attempt {attempt + 1} sending '{method}' request to '{url}'"
        )
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.TransportError as err:
            if attempt < attempts:
                await asyncio.sleep((attempt + 1) * 0.1)
                continue
            else:
                raise err
        else:
            return response




# async def async_get(
#         async_client: httpx.AsyncClient,
#         url: str,
#         retries: int = 2,
#         raise_for_status: bool = True,
#         **kwargs
# ) -> httpx.Response:
#     """Send a HTTP GET request using httpx.

#     Parameters
#     ----------
#     url : str
#         Target url.
#     async_client : httpx.AsyncClient
#         Async client.
#     retries : int, optional
#         Number of retries in case of a transport error. The default is 2.
#     raise_for_status : bool, optional
#         If True call raise_for_status on the response. The default is True.
#     **kwargs : dict, optional
#         Extra arguments to httpx.AsyncClient.get(**kwargs).

#     Raises
#     ------
#     err : httpx.TransportError
#         Transport error.

#     Returns
#     -------
#     resp : httpx.Response
#         HTTP GET response.

#     """
#     for attempt in range(1, retries+2):
#         _base_msg = f"HTTP GET Attempt #{attempt}: {url}"
#         try:
#             resp = await async_client.get(url, **kwargs)
#             if raise_for_status:
#                 resp.raise_for_status()
#         except httpx.TransportError as err:
#             if attempt >= retries+1:
#                 _LOGGER.debug(f"{_base_msg}: Transport Error: {err}")
#                 raise err
#             else:
#                 await asyncio.sleep(attempt * 0.10)
#                 continue
#         else:
#             _LOGGER.debug(
#                 f"{_base_msg}: Response: {resp}: length: {len(resp.text)}"
#             )
#             return resp


# async def async_post(
#         async_client:  httpx.AsyncClient,
#         url: str,
#         retries: int = 2,
#         raise_for_status: bool = True,
#         **kwargs,
# ) -> httpx.Response:
#     """Send a HTTP POST request using httpx.

#     Parameters
#     ----------
#     url : str
#         Target url.
#     async_client : httpx.AsyncClient
#         Async client.
#     retries : int, optional
#         Number of reties in case of a transport error. The default is 2.
#     raise_for_status : bool, optional
#         If True call raise_for_status on the response. The default is True.
#     **kwargs : dict, optional
#         Extra arguments to httpx.AsyncClient.get(**kwargs).

#     Returns
#     -------
#     resp : httpx.Response
#         httpx response object.

#     """
#     for attempt in range(1, retries+2):
#         _base_msg = f"HTTP GET Attempt #{attempt}: {url}"
#         try:
#             resp = await async_client.post(url, **kwargs)
#             _LOGGER.debug(
#                 f"Response: HTTP POST #{attempt}: {resp}: {resp.text}"
#             )
#             if raise_for_status:
#                 resp.raise_for_status()
#         except httpx.TransportError as err:
#             if attempt >= retries+1:
#                 _LOGGER.debug(f"{_base_msg}: Transport Error: {err}")
#                 raise err
#             else:
#                 await asyncio.sleep(attempt * 0.10)
#                 continue
#         else:
#             _LOGGER.debug(
#                 f"{_base_msg}: Response: {resp}: length: {len(resp.text)}"
#             )
#             return resp
