"""The setlist.fm integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, CONF_USERID, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up setlist.fm from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SetlistFmCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register a single shared refresh service, guarded against double-registration
    if not hass.services.has_service(DOMAIN, "refresh"):
        async def handle_refresh(call) -> None:
            """Force refresh of data for a config entry."""
            entry_id = call.data.get("entry_id")
            if entry_id and entry_id in hass.data[DOMAIN]:
                await hass.data[DOMAIN][entry_id].async_request_refresh()
            else:
                # Refresh all entries if no specific entry_id given
                for coord in hass.data[DOMAIN].values():
                    if isinstance(coord, SetlistFmCoordinator):
                        await coord.async_request_refresh()

        hass.services.async_register(DOMAIN, "refresh", handle_refresh)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove the shared service only when the last entry is unloaded
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "refresh")

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class SetlistFmCoordinator(DataUpdateCoordinator):
    """Class to manage fetching setlist.fm data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.userid = entry.data[CONF_USERID]
        self.api_key = entry.data[CONF_API_KEY]

        refresh_hours = entry.options.get("refresh_period", 6)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.userid}",
            update_interval=timedelta(hours=refresh_hours),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

        # Use HA-managed session — properly closed on unload, uses HA's SSL context
        session = async_get_clientsession(self.hass)

        # Fetch user data
        user_url = f"https://api.setlist.fm/rest/1.0/user/{self.userid}"

        try:
            async with session.get(user_url, headers=headers) as response:
                if response.status == 401:
                    raise ConfigEntryAuthFailed("Invalid API key")
                elif response.status == 404:
                    raise UpdateFailed(f"User {self.userid} not found")
                elif response.status != 200:
                    raise UpdateFailed(
                        f"Error fetching user data: {response.status}"
                    )
                user_data = await response.json()

        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error connecting to setlist.fm: {err}") from err

        # Fetch attended concerts with retry logic for rate limiting
        attended_url = f"https://api.setlist.fm/rest/1.0/user/{self.userid}/attended"

        # Initialise before the loop so the variable is always bound
        concerts_data: dict = {}

        for attempt in range(3):
            try:
                async with session.get(attended_url, headers=headers) as response:
                    if response.status == 200:
                        concerts_data = await response.json()
                        break
                    elif response.status == 429:
                        if attempt < 2:
                            _LOGGER.warning(
                                "Rate limit exceeded, retrying in 5 seconds (attempt %d/3)",
                                attempt + 1,
                            )
                            await asyncio.sleep(5)
                            continue
                        else:
                            raise UpdateFailed("Rate limit exceeded after 3 attempts")
                    elif response.status == 401:
                        raise ConfigEntryAuthFailed("Invalid API key")
                    else:
                        raise UpdateFailed(
                            f"Error fetching concerts: {response.status}"
                        )

            except (ConfigEntryAuthFailed, UpdateFailed):
                raise
            except Exception as err:
                if attempt < 2:
                    _LOGGER.warning(
                        "Connection error, retrying (attempt %d/3): %s",
                        attempt + 1,
                        err,
                    )
                    await asyncio.sleep(5)
                    continue
                raise UpdateFailed(f"Error connecting to setlist.fm: {err}") from err

        return {
            "user": user_data,
            "concerts": concerts_data.get("setlist", []),
        }
