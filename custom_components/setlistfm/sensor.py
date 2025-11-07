"""Sensor platform for setlist.fm integration."""
from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SetlistFmCoordinator
from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_NUMBER_OF_CONCERTS,
    CONF_DATE_FORMAT,
    CONF_SHOW_CONCERTS,
    DEFAULT_NUMBER_OF_CONCERTS,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SHOW_CONCERTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up setlist.fm sensors based on a config entry."""
    coordinator: SetlistFmCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Use simple English strings (translations can be added later via HA's system)
    at_str = "at"
    in_str = "in"
    on_str = "on"
    upcoming_str = "Upcoming"
    
    translation_strings = {
        "at": at_str,
        "in": in_str,
        "on": on_str,
        "upcoming": upcoming_str,
    }
    
    entities = [
        SetlistFmConcertsSensor(coordinator, entry, translation_strings),
        SetlistFmLastUpdateSensor(coordinator, entry),
    ]
    
    async_add_entities(entities)


class SetlistFmConcertsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a setlist.fm concerts sensor."""

    def __init__(
        self,
        coordinator: SetlistFmCoordinator,
        entry: ConfigEntry,
        translation_strings: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._translation_strings = translation_strings
        self._userid = entry.data["userid"]
        self._attr_name = f"{entry.data.get(CONF_NAME, entry.data['userid'])} Concerts"
        self._attr_unique_id = f"{entry.entry_id}_concerts"
        # Use userid for entity_id
        self.entity_id = f"sensor.setlistfm_{self._userid}_concerts"
        self._attr_icon = "mdi:music-note"

    @property
    def native_value(self) -> int:
        """Return the number of concerts."""
        if self.coordinator.data is None:
            return 0
        
        concerts = self._get_filtered_concerts()
        return len(concerts)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
        
        concerts = self._get_filtered_concerts()
        concert_lines = self._format_concerts(concerts)
        
        # Create simplified concert list for attributes
        simplified_concerts = []
        for concert in concerts:
            try:
                artist_name = concert.get("artist", {}).get("name", "Unknown")
                venue_name = concert.get("venue", {}).get("name", "Unknown")
                city_name = concert.get("venue", {}).get("city", {}).get("name", "")
                state = concert.get("venue", {}).get("city", {}).get("state", "")
                country = concert.get("venue", {}).get("city", {}).get("country", {}).get("name", "")
                
                # Count songs
                song_count = 0
                sets = concert.get("sets", {}).get("set", [])
                for set_item in sets:
                    songs = set_item.get("song", [])
                    song_count += len(songs)
                
                simplified_concerts.append({
                    "id": concert.get("id"),
                    "date": concert.get("eventDate"),
                    "artist": {
                        "name": artist_name,
                        "mbid": concert.get("artist", {}).get("mbid"),
                    },
                    "venue": {
                        "name": venue_name,
                        "city": city_name,
                        "state": state,
                        "country": country,
                    },
                    "song_count": song_count,
                    "url": concert.get("url", ""),
                })
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Error simplifying concert data: %s", err)
                continue
        
        return {
            "concerts": simplified_concerts,
            "concert_list": "\n".join(concert_lines),
        }

    def _get_filtered_concerts(self) -> list:
        """Get filtered and sorted concerts based on options."""
        if self.coordinator.data is None:
            return []
        
        concerts = self.coordinator.data.get("concerts", [])
        options = self._entry.options
        
        show_concerts = options.get(CONF_SHOW_CONCERTS, DEFAULT_SHOW_CONCERTS)
        number_of_concerts = options.get(CONF_NUMBER_OF_CONCERTS, DEFAULT_NUMBER_OF_CONCERTS)
        
        # Sort concerts by date, newest first
        try:
            concerts_sorted = sorted(
                concerts,
                key=lambda x: datetime.strptime(x["eventDate"], "%d-%m-%Y"),
                reverse=True,
            )
        except (KeyError, ValueError) as err:
            _LOGGER.error("Error sorting concerts: %s", err)
            return []
        
        # Filter based on show_concerts option
        now = dt_util.now().date()
        filtered = []
        
        for concert in concerts_sorted:
            try:
                event_date = datetime.strptime(concert["eventDate"], "%d-%m-%Y").date()
                
                if show_concerts == "upcoming" and event_date >= now:
                    filtered.append(concert)
                elif show_concerts == "past" and event_date < now:
                    filtered.append(concert)
                elif show_concerts == "all":
                    filtered.append(concert)
                
                if len(filtered) >= number_of_concerts:
                    break
            
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Error processing concert: %s", err)
                continue
        
        return filtered

    def _format_concerts(self, concerts: list) -> list:
        """Format concerts into readable strings."""
        options = self._entry.options
        date_format = options.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)
        now = dt_util.now().date()
        
        lines = []
        for concert in concerts:
            try:
                event_date = datetime.strptime(concert["eventDate"], "%d-%m-%Y").date()
                formatted_date = event_date.strftime(date_format)
                
                artist_name = concert.get("artist", {}).get("name", "Unknown Artist")
                venue_name = concert.get("venue", {}).get("name", "Unknown Venue")
                city_name = concert.get("venue", {}).get("city", {}).get("name", "")
                
                line = f"{artist_name} {self._translation_strings['at']} {venue_name}"
                
                if city_name:
                    line += f" {self._translation_strings['in']} {city_name}"
                
                line += f" {self._translation_strings['on']} {formatted_date}"
                
                if event_date > now:
                    line += f" ({self._translation_strings['upcoming']})"
                
                lines.append(line)
            
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Error formatting concert: %s", err)
                continue
        
        return lines


class SetlistFmLastUpdateSensor(CoordinatorEntity, SensorEntity):
    """Representation of the last update sensor."""

    def __init__(
        self,
        coordinator: SetlistFmCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._userid = entry.data["userid"]
        self._attr_name = f"{entry.data.get(CONF_NAME, entry.data['userid'])} Last Update"
        self._attr_unique_id = f"{entry.entry_id}_last_update"
        # Use userid for entity_id
        self.entity_id = f"sensor.setlistfm_{self._userid}_last_update"
        self._attr_icon = "mdi:clock-outline"
        # Removed device_class to avoid configuration errors
        self._last_update_time = dt_util.now()

    @property
    def native_value(self) -> str:
        """Return the last update time as ISO string."""
        # Update the time whenever we get new data
        if self.coordinator.last_update_success:
            self._last_update_time = dt_util.now()
        return self._last_update_time.isoformat()

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        attrs = {
            "last_update_success": self.coordinator.last_update_success,
        }
        
        if self.coordinator.last_exception:
            attrs["last_error"] = str(self.coordinator.last_exception)
        
        return attrs
