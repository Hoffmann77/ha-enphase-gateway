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
CLEAN_SERIAL = "<<serial_number>>"

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    # CONF_TOKEN,
}


async def _get_fixtures(enreader: GatewayReader) -> dict[str, Any]:
    """Collect Envoy endpoints to use for test fixture set."""
    to_redact = enreader.auth.to_redact

    fixtures: dict[str, Any] = {}
    for endpoint in FIXTURE_COLLECTION_ENDPOINTS:
        response = await enreader.request(endpoint)

        data = {
            "request": {
                "url": str(response.request.url),
                "method": response.request.method,
                "headers": dict(response.request.headers.items()),
            },
            "response": {
                "url": str(response.url),
                "status_code": response.status_code,
                "reason_phrase": response.reason_phrase,
                "is_redirect": response.is_redirect,
                "encoding": response.encoding,
                "headers": dict(response.headers.items()),
                "cookies": dict(response.cookies.items()),
            }
        }

        # request_data = {
        #     "url": str(response.request.url),
        #     "method": response.request.method,
        #     "headers": dict(response.request.headers.items()),
        # }

        # response_data = {
        #     "url": str(response.url),
        #     "status_code": response.status_code,
        #     "reason_phrase": response.reason_phrase,
        #     "is_redirect": response.is_redirect,
        #     "encoding": response.encoding,
        #     "headers": dict(response.headers.items()),
        #     "cookies": dict(response.cookies.items()),
        # }

        # Redact sensitive data from the metadata.
        redacted = json_dumps(data)
        for to_replace, placeholder in to_redact:
            redacted.replace(to_replace, placeholder)

        redacted_data = json_loads(redacted)

        # Decode the response content into text.
        # Use `backslashreplace` so we do not lose any data.
        response_text = response.content.decode(
            encoding="utf-8", errors="backslashreplace"
        )

        # Redact the serial number from the response text.
        response_text.replace(enreader.serial_number, CLEAN_SERIAL)

        redacted_data["response"]["text"] = response_text
        fixtures[endpoint] = {"default": redacted_data}

    return fixtures


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Make sure the integration is ready to provide useful diagnostics.
    if TYPE_CHECKING:
        assert coordinator.gateway.initial_update_finished

    # Get the reader instance
    enreader = coordinator.gateway_reader

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Collect every entity and information about the entity's state
    # that is associated with the given config entry.
    device_entities = []
    for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
    ):
        entities = []
        for entity in er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        ):
            state_dict = None
            if state := hass.states.get(entity.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)
            entity_dict = asdict(entity)
            entity_dict.pop("_cache", None)
            entities.append(
                {"entity": entity_dict, "state": state_dict}
            )

        device_dict = asdict(device)
        device_dict.pop("_cache", None)
        device_entities.append({"device": device_dict, "entities": entities})

    # Clean the data by removing the serial number.
    device_entities = json_dumps(device_entities).replace(
        enreader.serial_number, CLEAN_SERIAL
    )

    # Clean the raw data that has been fetched from the endpoints.
    gateway_raw_data = copy.deepcopy(enreader.gateway.data)
    gateway_raw_data = json_dumps(gateway_raw_data).replace(
        enreader.serial_number, CLEAN_SERIAL
    )

    gateway_info: dict[str, Any] = {
        "Firmware version": enreader._info.firmware_version,
        "Part number": enreader._info.part_number,
        "imeter": enreader._info.imeter,
        "web_tokens": enreader._info.web_tokens,
        "Detected gateway class": enreader.gateway.__class__.__name__,
        "Authentication class": enreader.auth.__class__.__name__,
    }

    fixtures: dict[str, Any] = {}
    if entry.options.get(OPTION_DIAGNOSTICS_INCLUDE_FIXTURES, False):
        try:
            fixtures = await _get_fixtures(enreader)
        except Exception as err:
            fixtures["Error"] = repr(err)

    diagnostic_data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "gateway_info": gateway_info,
        "gateway_raw_data": json_loads(gateway_raw_data),
        "entities_by_device": json_loads(device_entities),
        "fixtures": fixtures,
    }

    return diagnostic_data
