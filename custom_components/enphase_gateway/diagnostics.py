"""Diagnostics support for the Enphase Gateway component."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from attr import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

from .const import (
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
    FIXTURE_COLLECTION_ENDPOINTS,
)

from .coordinator import EnphaseConfigEntry
from .enreader import GatewayReader

CONF_TITLE = "title"
CLEAN_SERIAL = "<<envoyserial>>"

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    # CONF_TOKEN,
}


async def _get_fixtures(reader: GatewayReader, serial: str) -> dict[str, Any]:
    """Collect Envoy endpoints to use for test fixture set."""
    fixtures: dict[str, Any] = {}
    for endpoint in FIXTURE_COLLECTION_ENDPOINTS:
        response = await reader.request(endpoint)

        # Probably not needed.
        # request_meta: dict[str, Any] = {
        #     "url": str(response.request.url),
        #     "method": response.request.method,
        #     "headers": dict(response.headers.items()),
        #     # "cookies": dict(response.cookies.items()),
        # }

        response_meta: dict[str, Any] = {
            "url": str(response.url),
            "status_code": response.status_code,
            "reason_phrase": response.reason_phrase,
            "encoding": response.encoding,
            "headers": dict(response.headers.items()),
            # "cookies": dict(response.cookies.items()),
        }

        # Replace the serial number.
        response_text = response.text.replace(serial, CLEAN_SERIAL)

        fixtures[endpoint] = {
            "response_meta": response_meta,
            "response_text": response_text,
        }

    return fixtures


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Make sure the integration is ready to provide useful diagnostics.
    if TYPE_CHECKING:
        assert coordinator.gateway.initial_update_finished

    reader = coordinator.gateway_reader

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    #
    # Collect every entity and information about the entity's state
    # that is associated with the given config entry.
    #
    entities = []

    _devices = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )
    for device in _devices:
        device_entities = []
        _entities = er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        )
        for entity in _entities:
            state_dict = None
            if state := hass.states.get(entity.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)
            entity_dict = asdict(entity)
            entity_dict.pop("_cache", None)
            device_entities.append(
                {"entity": entity_dict, "state": state_dict}
            )

        device_dict = asdict(device)
        device_dict.pop("_cache", None)
        entities.append({"device": device_dict, "entities": entities})

    # Clean the data by removing the serial number.
    serial_num = coordinator.reader.serial_number
    coordinator_data = copy.deepcopy(coordinator.data)
    coordinator_data_cleaned = json_dumps(coordinator_data).replace(
        serial_num, CLEAN_SERIAL
    )
    device_entities_cleaned = json_dumps(device_entities).replace(
        serial_num, CLEAN_SERIAL
    )

    # The data that is available to the gateway for parsing.
    gateway_data: dict[str, Any] = reader.data

    debug_info: dict[str, Any] = {
        "Firmware version": reader._info.firmware_version,
        "Part number": reader._info.part_number,
        "imeter": reader._info.imeter,
        "web_tokens": reader._info.web_tokens,
        "Detected gateway class": reader.gateway.__class__.__name__,
        "Authentication class": reader.auth.__class__.__name__,
    }

    fixtures: dict[str, Any] = {}
    if entry.options.get(OPTION_DIAGNOSTICS_INCLUDE_FIXTURES, False):
        try:
            fixtures = await _get_fixtures(reader, serial_num)
        except Exception as err:
            fixtures["Error"] = repr(err)

    diagnostic_data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "debug_info": debug_info,
        "raw_data": json_loads(coordinator_data_cleaned),
        "gateway_data": gateway_data,
        "entities_by_device": json_loads(device_entities_cleaned),
        "fixtures": fixtures,
    }

    return diagnostic_data
