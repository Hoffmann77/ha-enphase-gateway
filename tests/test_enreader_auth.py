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

from custom_components.enphase_gateway.enreader import auth, GatewayReader
from custom_components.enphase_gateway.enreader import gateway
from .enreader_common import (
    get_mock_enreader,
    GatewayFixture,
)

LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "version, auth_class, gateway_class",
    [
         ("3.7.0", auth.LegacyAuth, gateway.EnvoyLegacy),
         ("3.9.36", auth.LegacyAuth, gateway.Envoy),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_auth(version: str, auth_class, gateway_class) -> None:
    """Test the authentication process."""
    fixture = GatewayFixture(version)
    fixture.mock_auth_endpoints()

    enreader = GatewayReader("127.0.0.1")

    await enreader.authenticate("username", "password")

    assert isinstance(enreader.auth, auth_class)
    assert isinstance(enreader.gateway, gateway_class)
