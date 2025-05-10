
import json
import httpx




def _retrieve_token() -> str:
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
    LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
    TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"


    # client = httpx.Client(verify=False)

    # response = client.get("http://envoy.local/info")

    # data = json.loads(response.content)

    # return

    with httpx.Client(verify=True) as client:
        # Login to Enlighten to obtain a session ID.
        response = client.post(
            LOGIN_URL,
            data={
                "user[email]": "",
                "user[password]": "",
            }
        )

        meta = {
            "request": {
                "url": str(response.request.url),
                "method": response.request.method,
                "headers": dict(response.request.headers.items()),
            },
            "response": {
                "url": str(response.url),
                "status_code": response.status_code,
                "reason_phrase": response.reason_phrase,
                "encoding": response.encoding,
                "headers": dict(response.headers.items()),
                "cookies": dict(response.cookies.items()),
            },
        }

        abnormal = "password_wrong"

        with open(f"enlighten/login_meta_{abnormal}.json", 'w') as f:
            json.dump(meta, f)

        with open(f"enlighten/login_response_{abnormal}", 'w') as f:
            f.write(response.text)

        return

        enlighten_data = json.loads(response.text)

        # enlighten_data = {}
        # enlighten_data["session_id"] = ""

        # Use the session ID to retrieve a new token.
        response = client.post(
            TOKEN_URL,
            json={
                #"session_id": enlighten_data["session_id"],
                "serial_num": "",
                "username": ""
            }
        )

        meta = {
            "request": {
                "url": str(response.request.url),
                "method": response.request.method,
                "headers": dict(response.request.headers.items()),
            },
            "response": {
                "url": str(response.url),
                "status_code": response.status_code,
                "reason_phrase": response.reason_phrase,
                "encoding": response.encoding,
                "headers": dict(response.headers.items()),
                "cookies": dict(response.cookies.items()),
            },
        }

        abnormal = "missing_session_id"

        with open(f"token_meta_{abnormal}.json", 'w') as f:
            json.dump(meta, f)

        with open(f"token_response_{abnormal}", 'w') as f:
            f.write(response.text)








_retrieve_token()



# async def _async_post_enlighten(
#         self,
#         async_client: httpx.AsyncClient,
#         url: str,
#         **kwargs,
# ) -> httpx.Response:
#     """Send a HTTP POST request to Enlighten.

#     Parameters
#     ----------
#     async_client : httpx.AsyncClient
#         Async httpx client.
#     url : str
#         Target url.
#     **kwargs : dict, optional
#         Extra arguments to httpx.

#     Raises
#     ------
#     EnlightenCommunicationError
#         Raised for httpx transport Errors.
#     EnlightenAuthenticationError
#         Raised if the Enlighten credentials are invalid.

#     Returns
#     -------
#     resp : httpx.Response
#         HTTP response.

#     """
#     try:
#         resp = await async_post(async_client, url, **kwargs)
#     except httpx.TransportError as err:
#         raise EnlightenCommunicationError(
#             "Error communicating with the Enlighten platform",
#             request=err.request,
#         ) from err
#     except httpx.HTTPStatusError as err:
#         if err.response.status_code == 401:
#             raise EnlightenAuthenticationError(
#                 "Invalid Enlighten credentials",
#                 request=err.request,
#                 response=err.response,
#             ) from err
#     else:
#         return resp
