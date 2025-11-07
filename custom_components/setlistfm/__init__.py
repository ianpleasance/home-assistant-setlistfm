"""The setlist.fm integration."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
import aiohttp

from .const import DOMAIN, CONF_USERID, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up setlist.fm from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    coordinator = SetlistFmCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    # Register service
    async def force_refresh(call):
        """Force refresh of data."""
        _LOGGER.debug("Force refresh service called for entry %s", entry.entry_id)
        await coordinator.async_request_refresh()
    
    hass.services.async_register(DOMAIN, f"force_refresh_{entry.entry_id}", force_refresh)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Unregister service
        hass.services.async_remove(DOMAIN, f"force_refresh_{entry.entry_id}")
    
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
        
        async with aiohttp.ClientSession() as session:
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
            
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Error connecting to setlist.fm: {err}") from err
            
            # Fetch attended concerts with retry logic for rate limiting
            attended_url = f"https://api.setlist.fm/rest/1.0/user/{self.userid}/attended"
            
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
                
                except aiohttp.ClientError as err:
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
