"""Common test functions for the enreader package."""

import json
from pathlib import Path
from typing import Any

import jwt
import orjson
import respx
from httpx import Response

from custom_components.enphase_gateway.enreader import GatewayReader


async def get_mock_enreader(self, update: bool = True, token: str | None = None):
    """Return a mock gateway reader."""
    enreader = GatewayReader(host="127.0.0.1")
    await enreader.authenticate("username", "password", token)
    if update:
        await enreader.update()
        await enreader.update()

    return enreader


class GatewayFixture:

    def __init__(self, version: str):
        self.version = version
        self._meta = None

    @property
    def meta(self):
        """Return the metadata."""
        if self._meta:
            return self._meta

        self._meta = json.loads(self._load_fixture("version_meta.json"))
        return self._meta

    @property
    def _fixture_dir(self):
        """Return the directory holding the fixtures for this version."""
        path = Path(__file__).parent.joinpath("fixtures_V2", self.version)
        if not path.exists():
            raise Exception

        return path

    def mock_info_endpoint(self):
        """Set up the response mock for the /info endpoint."""
        self.mock("/info")

    def mock_auth_endpoints(self, mock_enlighten: bool = False):
        """Set up the response mocks for the authentication endpoints."""
        jwt_token = jwt.encode(
            payload={"name": "mock_token", "exp": 1707837780},
            key="secret",
            algorithm="HS256",
        )

        if mock_enlighten:
            respx.post(
                "https://enlighten.enphaseenergy.com/login/login.json?"
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "session_id": "1234567890",
                        "user_id": "1234567890",
                        "user_name": "test",
                        "first_name": "Test",
                        "is_consumer": True,
                        "manager_token": "1234567890",
                    },
                )
            )
            respx.post("https://entrez.enphaseenergy.com/tokens").mock(
                return_value=Response(200, text=jwt_token)
            )
            respx.get("/auth/check_jwt").mock(
                return_value=Response(
                    200, text="<!DOCTYPE html><h2>Valid token.</h2>"
                )
            )

    def mock_endpoints(self, endpoints: list[str]):
        """Set up the response mocks for the given endpoints."""
        for endpoint in endpoints:
            self.mock(endpoint)

    def mock(self, endpoint: str, behaviour: str = "default"):
        """Mock the endpoint."""
        endpoint_data = self.meta["endpoints"][endpoint][behaviour]
        request_data = endpoint_data["request"]
        response_data = endpoint_data["response"]

        if (text := response_data.get("text")) is None:
            text = self._load_fixture(response_data["text_path"])

        method = request_data.get("method", "GET")

        # Encode the text into bytes so we can use the `content` kwarg.
        # Using the `text` kwarg would modify the content_type header.
        content = text.encode(errors="backslashreplace")

        respx.request(method, endpoint).mock(
            return_value=Response(
                response_data["status_code"],
                headers=response_data.get("headers"),
                content=content,
            )
        )

    def _load_fixture(self, fpath: str):
        """Load the fixture."""
        with open(self._fixture_dir.joinpath(fpath)) as f:
            return f.read()
