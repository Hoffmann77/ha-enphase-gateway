"""Testing module."""

import json
import logging
from pathlib import Path

import respx
import pytest
from httpx import Response

# from custom_components.enphase_gateway.gateway_reader import GatewayReader
# from custom_components.enphase_gateway.gateway_reader.auth import LegacyAuth
from custom_components.enphase_gateway.enreader import GatewayReader
from custom_components.enphase_gateway.enreader.auth import LegacyAuth
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

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
@respx.mock
async def test_with_3_7_0_firmware() -> None:
    """Test the authentication process."""
    fixture = GatewayFixture("3.7.0")
    fixture.mock_auth_endpoints(mock_enlighten=False)

    enreader = GatewayReader("127.0.0.1")
    enreader.auth = LegacyAuth(
        enreader.host,
        "username",
        "password",
    )

    # Get the endpoints required for probing
    info = await enreader._get_info()
    gateway = await enreader._detect_gateway(info)

    # Mock the endpoints required for probing
    fixture.mock_endpoints(
        [endpoint.path for endpoint in gateway.probing_endpoints]
    )

    enreader.gateway = await enreader._probe_gateway(gateway)

    # Mock the endpoints required for probing
    fixture.mock_endpoints(
        [endpoint.path for endpoint in enreader.gateway.required_endpoints]
    )

    # Update twice
    enreader.update()
    enreader.update()

    assert isinstance(enreader.gateway, EnvoyLegacy)

    # production data
    assert gateway.production == 6.63 * 1000
    assert gateway.daily_production == 53.6 * 1000
    assert gateway.seven_days_production == 405 * 1000
    assert gateway.lifetime_production == 133 * 1000000



# @pytest.mark.asyncio
# @respx.mock
# async def test_with_3_7_0_firmware():
#     """Test with 3.7.0 firmware.

#     Fixtures represent an Envoy-R with the old firmware.

#     """
#     fixture = GatewayFixture("3.7.0")
    
#     enreader = GatewayReader("127.0.0.1")
    
#     fixture_name = "3.7.0_envoy_r"
#     gateway_class = "EnvoyLegacy"

#     gateway = await get_gateway(fixture_name)

#     assert gateway.__class__.__name__ == gateway_class
#     print(gateway.data)

#     # production data
#     assert gateway.production == 6.63 * 1000
#     assert gateway.daily_production == 53.6 * 1000
#     assert gateway.seven_days_production == 405 * 1000
#     assert gateway.lifetime_production == 133 * 1000000


# @pytest.mark.asyncio
# @respx.mock
# async def test_with_3_9_36_firmware():
#     """Test with 3.9.36 firmware.

#     Fixtures represent an Envoy-R with the new firmware.

#     """
#     # Config --->
#     fixture_name = "3.9.36_envoy_r"
#     gateway_class = "Envoy"

#     gateway = await get_gateway(fixture_name)

#     assert gateway.__class__.__name__ == gateway_class

#     # production data
#     assert gateway.production == 1271
#     assert gateway.daily_production == 1460
#     assert gateway.seven_days_production == 130349
#     assert gateway.lifetime_production == 6012540
#     # inverters
#     assert gateway.inverters["121547060495"] == {
#         "serialNumber": "121547060495",
#         "lastReportDate": 1618083959,
#         "lastReportWatts": 135,
#         "maxReportWatts": 228
#     }


# @pytest.mark.asyncio
# @respx.mock
# async def test_with_7_6_175_firmware():
#     """Test with 7.6.175 firmware.

#     Fixtures represent an Envoy-S Metered in a normal configuration.

#     """
#     # Config --->
#     fixture_name = "7.6.175_envoy_s_metered"
#     gateway_class = "EnvoySMetered"

#     gateway = await get_gateway(fixture_name)

#     # gateway class
#     assert gateway.__class__.__name__ == gateway_class
#     # meter configuration
#     assert gateway.production_meter == 704643328
#     assert gateway.net_consumption_meter == 704643584
#     assert gateway.total_consumption_meter is None
#     # production data
#     assert gateway.production == 488.925
#     assert gateway.daily_production == 4425.303
#     # assert gateway.seven_days_production == 111093.303 #HINT: disabled
#     assert gateway.lifetime_production == 3183793.885
#     # consumption data
#     assert gateway.consumption == (488.925 - 36.162)
#     assert gateway.daily_consumption == 19903.621
#     # assert gateway.seven_days_consumption == 4.621 #HINT: disabled
#     assert gateway.lifetime_consumption == (
#         3183793.885 - (1776768.769 - 3738205.282)
#     )
#     # battery data
#     assert gateway.ensemble_inventory is None
#     assert gateway.ensemble_power is None
#     # inverters
#     assert gateway.inverters["482243031579"] == {
#         "serialNumber": "482243031579",
#         "lastReportDate": 1693744825,
#         "devType": 1,
#         "lastReportWatts": 135,
#         "maxReportWatts": 365
#     }


# @pytest.mark.asyncio
# @respx.mock
# async def test_with_7_6_175_firmware_cts_disabled():
#     """Test with 7.6.175 firmware with disabled current transformers.

#     Fixtures represent an Envoy-S Metered where both the production and
#     the consumption meters are disabled.

#     """
#     # Config --->
#     fixture_name = "7.6.175_envoy_s_metered_cts_disabled"
#     gateway_class = "EnvoySMeteredCtDisabled"

#     gateway = await get_gateway(fixture_name)

#     # gateway class
#     assert gateway.__class__.__name__ == gateway_class
#     # meter configuration
#     assert gateway.production_meter is None
#     assert gateway.net_consumption_meter is None
#     assert gateway.total_consumption_meter is None
#     # production data
#     assert gateway.production == 1322
#     assert gateway.daily_production is None
#     # assert gateway.seven_days_production is None #HINT: disabled
#     assert gateway.lifetime_production == 1152866
#     # consumption data
#     assert gateway.consumption is None
#     assert gateway.daily_consumption is None
#     # assert gateway.seven_days_consumption is None #HINT: disabled
#     assert gateway.lifetime_consumption is None
#     # battery data
#     assert gateway.ensemble_inventory is None
#     assert gateway.ensemble_power is None
#     # inverters
#     assert gateway.inverters["122107032918"] == {
#         "serialNumber": "122107032918",
#         "lastReportDate": 1694181930,
#         "devType": 1,
#         "lastReportWatts": 21,
#         "maxReportWatts": 296
#     }
