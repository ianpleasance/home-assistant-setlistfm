"""Attendance snapshots and serialized refresh operations."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AttendanceData,
    SetlistFmAuthError,
    SetlistFmError,
    SetlistFmRateLimitError,
)
from .client import async_create_client
from .const import (
    CONF_API_KEY,
    CONF_REFRESH_PERIOD,
    CONF_USERID,
    DEFAULT_REFRESH_PERIOD,
    DOMAIN,
)
from .helpers import normalize_username
from .visits import ConcertVisits

_LOGGER = logging.getLogger(__name__)

type SetlistFmConfigEntry = ConfigEntry[SetlistFmCoordinator]


class RateLimitedUpdateFailed(UpdateFailed):
    """Retain a cooldown on HA versions without UpdateFailed(retry_after=...)."""

    def __init__(self, error: SetlistFmRateLimitError, now: float) -> None:
        super().__init__(str(error))
        self.retry_after = error.retry_after
        self.retry_at = now + error.retry_after


class SetlistFmCoordinator(DataUpdateCoordinator[AttendanceData]):
    """Fetch all advertised pages before publishing a new snapshot."""

    def __init__(self, hass: HomeAssistant, entry: SetlistFmConfigEntry) -> None:
        self.entry = entry
        self.userid = normalize_username(entry.data[CONF_USERID])
        self.api_key = entry.data[CONF_API_KEY]
        self.client = async_create_client(hass, self.api_key, self.userid)
        self.last_successful_update: datetime | None = None
        self._visits_data: AttendanceData | None = None
        self._visits: ConcertVisits | None = None
        self._refresh_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.userid}",
            update_interval=timedelta(
                hours=entry.options.get(CONF_REFRESH_PERIOD, DEFAULT_REFRESH_PERIOD)
            ),
        )
        self._unsub_shutdown = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
        )

    async def _async_handle_stop(self, event: Event) -> None:
        """Retire the timer on HA stop as well as on entry unload."""
        self._unsub_shutdown = None
        await self.async_shutdown()

    @callback
    def _schedule_refresh(self) -> None:
        """Use HA's single cancellable timer for polling and cooldown recovery."""
        # Newer HA also sets a one-shot delay from UpdateFailed. Consume it here
        # so both APIs use the same deadline and it cannot survive a later success.
        if hasattr(self, "_retry_after"):
            self._retry_after = None
        if (
            self._shutdown_requested
            or self.hass.is_stopping
            or not self._listeners
            or self.entry.pref_disable_polling
            or self._update_interval_seconds is None
        ):
            self._async_unsub_refresh()
            return

        interval = self._update_interval_seconds
        if not self.last_update_success and isinstance(
            self.last_exception, RateLimitedUpdateFailed
        ):
            # HA rounds loop.time() down before adding its jitter. One second
            # avoids early retries/zero-delay loops without shortening any delay.
            self._update_interval_seconds = (
                max(0, self.last_exception.retry_at - self.hass.loop.time()) + 1
            )
        try:
            super()._schedule_refresh()
        finally:
            self._update_interval_seconds = interval

    @property
    def concert_visits(self) -> ConcertVisits | None:
        """Share full-snapshot grouping, while date/option selection remains live."""
        if self.data is None:
            return None
        if self.data is not self._visits_data:
            self._visits = ConcertVisits(self.data)
            self._visits_data = self.data
        return self._visits

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Serialize scheduled, setup, debounced and direct coordinator work."""
        async with self._refresh_lock:
            if scheduled and (
                not self._listeners
                or self.entry.pref_disable_polling
                or self._update_interval_seconds is None
            ):
                return
            await super()._async_refresh(
                log_failures=log_failures,
                raise_on_auth_failed=raise_on_auth_failed,
                scheduled=scheduled,
                raise_on_entry_error=raise_on_entry_error,
            )

    async def async_manual_refresh(self) -> None:
        """Await this refresh and its result, without debouncer early returns."""
        # Hold the same lock through HA's data/error publication and inspection.
        # Locking only _async_update_data would let a later refresh change the result.
        async with self._refresh_lock:
            if self._shutdown_requested:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="entry_unloaded",
                )
            await super()._async_refresh(log_failures=True)
            if self._shutdown_requested:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="entry_unloaded",
                )
            if not self.last_update_success:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="refresh_failed",
                    translation_placeholders={
                        "entries": self.entry.title,
                        "error": str(self.last_exception),
                    },
                ) from self.last_exception

    async def _async_update_data(self) -> AttendanceData:
        """Timestamp completed retrievals, not reads or partial failed requests."""
        try:
            data = await self.client.async_get_attendance()
        except SetlistFmAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SetlistFmRateLimitError as err:
            raise RateLimitedUpdateFailed(err, self.hass.loop.time()) from err
        except SetlistFmError as err:
            raise UpdateFailed(str(err)) from err
        self.last_successful_update = dt_util.utcnow()
        self.last_exception = None
        return data

    @callback
    def async_update_local_date(self, now: datetime) -> None:
        """Re-evaluate date-based entities at local midnight without an API call."""
        self.async_update_listeners()
