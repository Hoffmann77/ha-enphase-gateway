"""The Enphase Envoy integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .enreader import GatewayReader
from .coordinator import GatewayUpdateCoordinator, EnphaseGatewayConfigEntry
from .const import (
    DOMAIN, PLATFORMS, CONF_ENCHARGE_ENTITIES, CONF_INVERTERS
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant, entry: EnphaseGatewayConfigEntry,
) -> bool:
    """Set up the Enphase Gateway component."""
    reader = GatewayReader(
        entry.data[CONF_HOST],
        get_async_client(hass, verify_ssl=False),
    )
    coordinator = GatewayUpdateCoordinator(hass, entry, reader)

    # Fetch initial data so we have data when entities subscribe.
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later.
    #
    await coordinator.async_config_entry_first_refresh()

    # TODO: verify this bit of code.
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=reader.serial_number
        )

    # Store the coordinator.
    entry.runtime_data = coordinator

    # Forward the Config Entry to the platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when it's updated.
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_update_listener(
        hass: HomeAssistant, entry: EnphaseGatewayConfigEntry,
) -> bool:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
    # !!! Prototype for deleting inverter entities after an options flow.
    # registry = entity_registry.async_get(hass)
    # entities = entity_registry.async_entries_for_config_entry(
    #     registry, entry.entry_id
    # )
    # for entity in entities:
    #     if entity.inverter_type != entry.options[CONF_INVERTERS]:
    #         registry.async_remove(entity.entity_id)


async def async_unload_entry(
        hass: HomeAssistant, entry: EnphaseGatewayConfigEntry,
) -> bool:
    """Unload a config entry."""
    coordinator: GatewayUpdateCoordinator = entry.runtime_data
    coordinator.async_cancel_token_refresh()

    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        # Remove the store data.
        await coordinator.async_remove_store(hass, entry)

    return unload


# async def async_remove_config_entry_device(
#         hass: HomeAssistant,
#         entry: EnphaseGatewayConfigEntry,
#         device_entry: dr.DeviceEntry,
# ) -> bool:
#     """Remove a config entry from a device."""
#     pass


async def async_migrate_entry(
        hass: HomeAssistant, entry: EnphaseGatewayConfigEntry
) -> bool:
    """Migrate the ConfigEntry."""
    _LOGGER.debug(f"Migrating from version {entry.version}")

    if entry.version == 1:
        pass

    _LOGGER.info("Migration to version {entry.version} successful.")

    return True
