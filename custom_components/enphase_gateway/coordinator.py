"""GatewayReader update coordinator."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING
from asyncio import sleep as asyncio_sleep

import httpx
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_TOKEN,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .enreader.auth import EnphaseTokenAuth
from .enreader.exceptions import (
    EnlightenAuthenticationError,
    GatewayAuthenticationRequired,
    GatewayAuthenticationError,
)


if TYPE_CHECKING:
    from .enreader import GatewayReader


SCAN_INTERVAL = timedelta(seconds=60)

STORAGE_KEY = "enphase_gateway"
STORAGE_VERSION = 1

TOKEN_REFRESH_CHECK_INTERVAL = timedelta(days=1)
STALE_TOKEN_THRESHOLD = timedelta(days=3).total_seconds()

_LOGGER = logging.getLogger(__name__)


type EnphaseGatewayConfigEntry = ConfigEntry[GatewayUpdateCoordinator]


class GatewayUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for gateway reader."""

    def __init__(
            self,
            hass: HomeAssistant,
            entry: ConfigEntry,
            gateway_reader: GatewayReader,
    ) -> None:
        """Initialize DataUpdateCoordinator for the gateway."""
        self.gateway_reader = gateway_reader
        self.config_entry = entry
        self._setup_complete = False
        self._cancel_token_refresh: CALLBACK_TYPE | None = None
        self._store = Store(
            hass,
            STORAGE_VERSION,
            ".".join([STORAGE_KEY, entry.entry_id]),
        )
        self._store_data = None
        self._store_update_pending = False
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            # always_update=False, # TODO: Added in ha 2023.9
        )

    async def async_remove_store(self, hass) -> None:
        """Remove all data from the store."""
        store = Store(
            hass,
            STORAGE_VERSION,
            ".".join([STORAGE_KEY, self.config_entry.entry_id]),
        )
        await store.async_remove()

    async def _async_setup_and_authenticate(self) -> None:
        """Set up the gateway_reader and authenticate."""
        token = await self._async_load_cached_token()
        if token:
            await self.gateway_reader.authenticate(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                token=token,
            )
            # The auth object is valid, but we still want
            # to refresh it if it's stale right away
            self._async_refresh_auth_if_needed()
            return

        await self.gateway_reader.authenticate(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
        )

        await self._async_update_cached_token()

    @callback
    def _async_refresh_auth_if_needed(self) -> None:
        """Proactively refresh the auth object if its stale."""
        if self.gateway_reader.auth.is_stale:
            self.hass.async_create_background_task(
                self._async_try_refresh_auth(),
                "{self.name} auth object refresh"
            )

    async def _async_try_refresh_auth(self) -> None:
        """Try to refresh the auth object."""
        try:
            await self.gateway_reader.auth.refresh()
        except:  # EnvoyError as err: # TODO: Error handling
            # If we can't refresh the token, we try again later.
            _LOGGER.debug(f"{self.name}: Error refreshing token")
            return
        else:
            await self._async_update_cached_token()

    @callback
    def _async_mark_setup_complete(self) -> None:
        """Mark setup as complete and setup token refresh if needed."""
        self._setup_complete = True
        if self._cancel_token_refresh:
            self._cancel_token_refresh()
            self._cancel_token_refresh = None
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return
        self._cancel_token_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_auth_if_needed,
            TOKEN_REFRESH_CHECK_INTERVAL,
            cancel_on_shutdown=True,
        )

    async def _async_load_cached_token(self) -> str | None:
        """Return the cached Enphase token.

        Returns
        -------
        str or None
            Return the Enphase token if available. Otherwise return `None`.

        """
        _LOGGER.debug(f"{self.name}: Loading cached token...")
        await self._async_sync_store(load=True)
        return self._store_data.get("token")

    async def _async_update_cached_token(self) -> None:
        """Update the cached token."""
        if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
            return

        _LOGGER.debug(f"{self.name}: Updating cached token.")
        if token := self.gateway_reader.auth.token:
            self._store_data["token"] = token
            self._store_update_pending = True
            await self._async_sync_store()

    async def _async_sync_store(self, load: bool = False) -> None:
        """Sync the store.

        Parameters
        ----------
        load : bool, optional
            Force the loading of the store. The default is False.

        """
        if (self._store and not self._store_data) or load:
            self._store_data = await self._store.async_load() or {}

        if self._store and self._store_update_pending:
            await self._store.async_save(self._store_data)
            self._store_update_pending = False

    # def _async_update_saved_token(self) -> None:
    #     """Update saved token in config entry."""
    #     if not isinstance(self.gateway_reader.auth, EnphaseTokenAuth):
    #         return
    #     # update token in config entry so we can
    #     # startup without hitting the Cloud API
    #     # as long as the token is valid
    #     _LOGGER.debug(f"{self.name}: Updating token in config entry from auth")
    #     self.hass.config_entries.async_update_entry(
    #         self.entry,
    #         data={
    #             **self.entry.data,
    #             CONF_TOKEN: self.gateway_reader.auth.token,
    #         },
    #     )

    async def _async_update_data(self) -> dict[str, Any]:

        gateway_reader = self.gateway_reader

        for _try in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
                    self._async_mark_setup_complete()
                await gateway_reader.update()
                return gateway_reader.gateway

            except GatewayAuthenticationError as err:  # TODO: improve
                # try to refresh cookies or get a new token
                # can also be done in the get method
                raise UpdateFailed(
                    f"Gateway authentication error: {err}"
                ) from err
                # continue

            except (EnlightenAuthenticationError, GatewayAuthenticationRequired) as err:
                # token likely expired or firmware changed - re-authenticate
                # Enlighten credentials are likely to be invalid
                if self._setup_complete and _try == 0:
                    self._setup_complete = False
                    continue
                raise ConfigEntryAuthFailed from err

            except httpx.HTTPError as err:
                # TODO: does this error occur at local time or utc?
                now = datetime.now(timezone.utc)
                if _try == 0 and now.hour == 23 and now.minute == 0:
                    asyncio_sleep(20)
                    continue
                raise UpdateFailed(
                    f"Error communicating with API: {err}"
                ) from err

        raise RuntimeError("Unreachable code in _async_update_data")
