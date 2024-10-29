
import json
import httpx




# test = "Häh"

# print(test.encode("utf-8"))

# v = json.dumps(test.encode("utf-8"))

# print(json.loads(v))



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


    client = httpx.Client(verify=True)

    resp = client.get("https://www.bitel.de/fileadmin/content/documents/pk_preislisten/pk-preislisten_05_24_09_23/BITel_Privatkunden_Preisliste_05_2024.pdf")

    # content_text = resp.text
    content_bytes = resp.content
    print(len(content_bytes))

    decoded = content_bytes.decode("utf-8", "ignore")

    decoded_encoded = decoded.encode("utf-8")

    print(len(decoded_encoded))

    # print(content)

    #bytes_encoded = content_text.encode("utf-8")
    #text_decoded = content_bytes.decode("utf-8")

    #with open('test_text_pdf', 'w') as f:
    #     f.write(content_text)

    #print(len(bytes_encoded))
    #print(len(text_decoded))

    return


    #return
    # Retrieve the session id from Enlighten.
    response = client.post(
        LOGIN_URL,
        data={
            'user[email]': "uvn@flap.de",
            'user[password]': "pw"
        },
        #cookies={"test": "test", "new": "new"},
        headers={"Authorization": f"Bearer token"}
    )

    request_meta = {
        "url": str(response.request.url),
        "method": response.request.method,
        "headers": dict(response.request.headers.items()),
    }

    response_meta = {
        "url": str(response.url),
        "status_code": response.status_code,
        "reason_phrase": response.reason_phrase,
        "encoding": response.encoding,
        "headers": dict(response.headers.items()),
        #"content": response.content,
         "cookies": dict(response.cookies.items()),
    }

    print(response_meta)
    return

    with open('response_content', 'wb') as f:
        f.write(response.content)

    with open('response_json.json', 'w') as f:

        json.dump(response.json(), f)

    with open('response_text.txt', 'w') as f:

        f.write(response.text)


    with open('response_meta.json', 'w') as f:
        json_file = {
            "request_meta": request_meta,
            "response_meta": response_meta,
        }
        json.dump(json_file, f)

    print(response.text)



    #response_data = json.loads(response.text)
    #_is_consumer = response_data["is_consumer"]
    #_manager_token = response_data["manager_token"]

    # # Retrieve the actual token from Enlighten using the session id.
    # resp = await self._async_post_enlighten(
    #     async_client,
    #     self.TOKEN_URL,
    #     json={
    #         'session_id': response_data['session_id'],
    #         'serial_num': self._gateway_serial_num,
    #         'username': self._enlighten_username
    #     }
    # )

    # return resp.text


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
