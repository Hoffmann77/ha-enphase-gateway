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


LOGGER = logging.getLogger(__name__)


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
async def test_auth(version: str, auth_class, gateway_class) -> None:
    """Test the authentication process."""
    fixture = GatewayFixture(version)
    fixture.mock_auth_endpoints(mock_enlighten=True)

    enreader = GatewayReader("127.0.0.1")

    # Get the endpoints required for probing
    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)
    to_mock = [endpoint.path for endpoint in gateway.probing_endpoints]

    # Mock the endpoints required for probing
    fixture.mock_probing_endpoints(to_mock)

    await enreader.authenticate("username", "password")

    assert isinstance(enreader.auth, auth_class)
    assert isinstance(enreader.gateway, gateway_class)
