"""The setlist.fm integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SetlistFmConfigEntry, SetlistFmCoordinator
from .frontend import async_register_frontend

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the shared action and cards independently of entry loading."""
    await async_register_frontend(hass)

    async def handle_refresh(call: ServiceCall) -> None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if "entry_id" in call.data:
            entry_id = call.data["entry_id"]
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is None
                or entry.domain != DOMAIN
                or entry.state is not ConfigEntryState.LOADED
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_entry",
                    translation_placeholders={"entry_id": entry_id},
                )
            entries = [entry]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_loaded_entries"
            )

        targets: list[tuple[str, SetlistFmCoordinator]] = [
            (entry.title, entry.runtime_data) for entry in entries
        ]
        failures: list[str] = []
        for title, coordinator in targets:
            try:
                await coordinator.async_manual_refresh()
            except HomeAssistantError as err:
                failures.append(f"{title}: {err}")
        if failures:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
                translation_placeholders={
                    "entries": ", ".join(title for title, _ in targets),
                    "error": "; ".join(failures),
                },
            )

    hass.services.async_register(
        DOMAIN,
        "refresh",
        handle_refresh,
        schema=vol.Schema({vol.Optional("entry_id"): cv.string}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SetlistFmConfigEntry) -> bool:
    """Set up the user's service device and coordinated platforms."""
    coordinator = SetlistFmCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    entry.async_on_unload(
        async_track_time_change(
            hass, coordinator.async_update_local_date, hour=0, minute=0, second=0
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SetlistFmConfigEntry) -> bool:
    """Unload platforms; HA runs registered coordinator/listener cleanup."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: SetlistFmConfigEntry) -> None:
    """Apply changed display and polling options."""
    await hass.config_entries.async_reload(entry.entry_id)
