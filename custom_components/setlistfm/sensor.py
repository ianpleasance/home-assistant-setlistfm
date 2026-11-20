"""Sensor platform for setlist.fm integration."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SetlistFmConfigEntry, SetlistFmCoordinator
from .entity import SetlistFmEntity
from .helpers import dated_concerts, select_dated, simplify_concert
from .const import (
    CONF_NUMBER_OF_CONCERTS,
    CONF_DATE_FORMAT,
    CONF_SHOW_CONCERTS,
    DEFAULT_NUMBER_OF_CONCERTS,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SHOW_CONCERTS,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

# Concert formatting strings — these are the English defaults used in concert_list.
# The translated equivalents live in translations/*.json under component.setlistfm.*
_AT = "at"
_IN = "in"
_ON = "on"
_UPCOMING = "Upcoming"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SetlistFmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up setlist.fm sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities = [
        SetlistFmConcertsSensor(coordinator, entry),
        SetlistFmTotalConcertsSensor(coordinator, entry),
        SetlistFmUniqueConcertVisitsSensor(coordinator, entry),
        SetlistFmNextConcertSensor(coordinator, entry),
        SetlistFmLastUpdateSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class SetlistFmConcertsSensor(SetlistFmEntity, SensorEntity):
    """Representation of a setlist.fm concerts sensor."""

    _attr_icon = "mdi:music-note"

    def __init__(
        self,
        coordinator: SetlistFmCoordinator,
        entry: SetlistFmConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "concerts")

    @property
    def native_value(self) -> int | None:
        """Return the number of concerts."""
        if self.coordinator.data is None:
            return None
        return len(self._get_filtered_concerts())

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}

        concerts = self._get_filtered_concerts()
        concert_lines = self._format_concerts(concerts)

        simplified_concerts = []
        for concert in concerts:
            try:
                simplified_concerts.append(simplify_concert(concert))
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Error simplifying concert data: %s", err)
                continue

        attrs = {
            ATTR_ATTRIBUTION: "Data provided by setlist.fm (https://www.setlist.fm)",
            "concerts": simplified_concerts,
            "concert_list": "\n".join(concert_lines),
            "last_updated": self.coordinator.last_successful_update,
            "last_update_success": self.coordinator.last_update_success,
            "total_attended": self.coordinator.data["total"],
            "fetched_count": self.coordinator.data["fetched_count"],
            "skipped_count": self.coordinator.data["skipped_count"],
            "complete": self.coordinator.data["complete"],
            "completeness_reason": self.coordinator.data["completeness_reason"],
        }
        if (visits := self.coordinator.concert_visits) is not None:
            attrs.update(visits.metadata)
            attrs["concert_visits"] = visits.display(
                dt_util.now().date(),
                self._entry.options.get(CONF_SHOW_CONCERTS, DEFAULT_SHOW_CONCERTS),
                self._entry.options.get(CONF_NUMBER_OF_CONCERTS, DEFAULT_NUMBER_OF_CONCERTS),
            )
        if self.coordinator.last_exception:
            attrs["last_error"] = str(self.coordinator.last_exception)
        return attrs

    def _get_filtered_concerts(self) -> list:
        """Get filtered and sorted concerts based on options."""
        if self.coordinator.data is None:
            return []

        concerts = self.coordinator.data.get("concerts", [])
        options = self._entry.options

        show_concerts = options.get(CONF_SHOW_CONCERTS, DEFAULT_SHOW_CONCERTS)
        number_of_concerts = options.get(CONF_NUMBER_OF_CONCERTS, DEFAULT_NUMBER_OF_CONCERTS)

        return select_dated(
            dated_concerts(concerts), dt_util.now().date(), show_concerts, number_of_concerts
        )

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

                line = f"{artist_name} {_AT} {venue_name}"
                if city_name:
                    line += f" {_IN} {city_name}"
                line += f" {_ON} {formatted_date}"
                if event_date > now:
                    line += f" ({_UPCOMING})"

                lines.append(line)

            except (KeyError, ValueError) as err:
                _LOGGER.warning("Error formatting concert: %s", err)
                continue

        return lines


class SetlistFmTotalConcertsSensor(SetlistFmEntity, SensorEntity):
    """The authoritative upstream total, not the displayed list length."""

    _attr_icon = "mdi:ticket"

    def __init__(
        self, coordinator: SetlistFmCoordinator, entry: SetlistFmConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "total_concerts")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data["total"] if self.coordinator.data is not None else None


class SetlistFmUniqueConcertVisitsSensor(SetlistFmEntity, SensorEntity):
    """Count known venue-days, independently of any display filter or limit."""

    _attr_icon = "mdi:calendar-check-outline"

    def __init__(
        self, coordinator: SetlistFmCoordinator, entry: SetlistFmConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "unique_concert_visits")

    @property
    def native_value(self) -> int | None:
        visits = self.coordinator.concert_visits
        return visits.count if visits is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        visits = self.coordinator.concert_visits
        if data is None or visits is None:
            return {}
        return {
            **visits.metadata,
            "complete": data["complete"],
            "completeness_reason": data["completeness_reason"],
            "fetched_count": data["fetched_count"],
            "skipped_count": data["skipped_count"],
        }


class SetlistFmNextConcertSensor(SetlistFmEntity, SensorEntity):
    """The earliest today-or-future setlist in the full available dataset."""

    _attr_icon = "mdi:calendar-music"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: SetlistFmCoordinator, entry: SetlistFmConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "next_concert")

    def _next_concert(self) -> tuple[date, dict[str, Any]] | None:
        if self.coordinator.data is None:
            return None
        today = dt_util.now().date()
        upcoming = (
            (datetime.strptime(concert["eventDate"], "%d-%m-%Y").date(), concert)
            for concert in self.coordinator.data["concerts"]
        )
        return min(
            (item for item in upcoming if item[0] >= today),
            key=lambda item: item[0],
            default=None,
        )

    @property
    def native_value(self) -> date | None:
        return concert[0] if (concert := self._next_concert()) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "complete": data["complete"] if data is not None else None,
            "completeness_reason": data["completeness_reason"] if data is not None else None,
        }
        if concert := self._next_concert():
            record = concert[1]
            attrs.update(
                artist=record.get("artist", {}).get("name", "Unknown"),
                venue=record.get("venue", {}).get("name", "Unknown"),
                url=record.get("url", ""),
            )
        return attrs


class SetlistFmLastUpdateSensor(SetlistFmEntity, SensorEntity):
    """A genuine completed retrieval timestamp, even when coverage is incomplete."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(
        self, coordinator: SetlistFmCoordinator, entry: SetlistFmConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "last_update")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_successful_update

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "last_update_success": self.coordinator.last_update_success,
        }
        if self.coordinator.last_exception:
            attrs["last_error"] = str(self.coordinator.last_exception)
        return attrs
