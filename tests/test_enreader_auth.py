"""Tests for the `enreader` auth module."""

import json
import logging
from os import listdir
from os.path import isfile, join
from unittest.mock import patch

import jwt
import pytest
import respx
from httpx import Response

from custom_components.enphase_gateway.enreader import GatewayReader
from custom_components.enphase_gateway.enreader.auth import (
    LegacyAuth,
    EnphaseTokenAuth
)
from custom_components.enphase_gateway.enreader.gateway import (
    EnvoyLegacy,
    Envoy,
    EnvoyS,
    EnvoySMetered,
)
from .enreader_common import (
    # get_mock_enreader,
    GatewayFixture,
)
from custom_components.enphase_gateway.enreader.exceptions import (
    EnlightenAuthenticationError,
    EnlightenCommunicationError,
    GatewayAuthenticationRequired,
)


_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
@respx.mock
async def test_missing_auth() -> None:
    """Test `authenticate()` gets called before `update()`."""
    enreader = GatewayReader(host="127.0.0.1")

    with pytest.raises(GatewayAuthenticationRequired):
        await enreader.update()


@pytest.mark.parametrize(
    "version, auth_class, gateway_class",
    [
         ("3.7.0", LegacyAuth, EnvoyLegacy),
         ("3.9.36", LegacyAuth, Envoy),
         ("7.6.175_standard", EnphaseTokenAuth, EnvoyS),
         ("7.6.175_metered", EnphaseTokenAuth, EnvoySMetered),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_auth_process(version: str, auth_class, gateway_class) -> None:
    """Test the authentication process."""
    fixture = GatewayFixture(version)
    fixture.mock_info_endpoint()
    fixture.mock_auth_endpoints(mock_enlighten=True)

    enreader = GatewayReader(host="127.0.0.1")

    # Get the endpoints required for probing
    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)
    to_mock = [endpoint.path for endpoint in gateway.probing_endpoints]

    # Mock the endpoints required for probing
    fixture.mock_endpoints(to_mock)

    await enreader.authenticate("username", "password")

    assert isinstance(enreader.auth, auth_class)
    assert isinstance(enreader.gateway, gateway_class)


@pytest.mark.parametrize(
    "username, password",
    [
         ("installer", ""),
         ("envoy", ""),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_legacy_auth_with_known_usernames(
        username: str,
        password: str,
) -> None:
    """Test the authentication process."""
    fixture = GatewayFixture("3.9.36")
    fixture.mock_info_endpoint()

    enreader = GatewayReader(host="127.0.0.1")

    # Detect the gateway class before we call `authenticate()`
    # so we can mock the endpoints used during authentication.
    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)

    # Mock the endpoints used during authentication.
    fixture.mock_endpoints(
        [endpoint.path for endpoint in gateway.probing_endpoints]
    )

    await enreader.authenticate(username, password)

    assert isinstance(enreader.auth, LegacyAuth)


@pytest.mark.parametrize(
    "version, gateway_class",
    [
         ("7.6.175_standard", EnvoyS),
         ("7.6.175_metered", EnvoySMetered),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_token_auth(version: str, gateway_class) -> None:
    """Test the authentication process."""
    fixture = GatewayFixture(version)
    fixture.mock_info_endpoint()
    fixture.mock_auth_endpoints(mock_enlighten=True)

    enreader = GatewayReader(host="127.0.0.1")

    # Get the endpoints required for probing
    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)
    to_mock = [endpoint.path for endpoint in gateway.probing_endpoints]

    # Mock the endpoints required for probing
    fixture.mock_endpoints(to_mock)

    await enreader.authenticate("username", "password")

    assert isinstance(enreader.auth, EnphaseTokenAuth)
    assert isinstance(enreader.gateway, gateway_class)


@pytest.mark.parametrize(
    "status_code, expected_error",
    [
         (401, EnlightenAuthenticationError),
         (403, EnlightenCommunicationError),
         (500, EnlightenCommunicationError),
         (503, EnlightenCommunicationError),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_token_retrieval_enlighten_error(
        status_code: int,
        expected_error,
) -> None:
    """Test that Enlighten HTTP errors raise a meaningful exception.

    A non-401 error from the Enlighten login endpoint previously caused
    `_async_post_enlighten` to return `None`, which then crashed with an
    opaque `AttributeError: 'NoneType' object has no attribute 'text'`.
    """
    fixture = GatewayFixture("7.6.175_standard")
    fixture.mock_info_endpoint()

    # Mock the Enlighten login endpoint to return an HTTP error.
    respx.post(
        "https://enlighten.enphaseenergy.com/login/login.json?"
    ).mock(return_value=Response(status_code))

    enreader = GatewayReader(host="127.0.0.1")

    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)
    fixture.mock_endpoints(
        [endpoint.path for endpoint in gateway.probing_endpoints]
    )

    with pytest.raises(expected_error):
        await enreader.authenticate("username", "password")


# expired token and no enlighten credentials
