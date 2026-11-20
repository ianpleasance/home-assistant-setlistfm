"""Shared identity and device information for native setlist.fm entities."""
from urllib.parse import quote

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import SetlistFmConfigEntry, SetlistFmCoordinator


class SetlistFmEntity(CoordinatorEntity[SetlistFmCoordinator]):
    """Keep entity and device registry identities stable across reloads."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SetlistFmCoordinator, entry: SetlistFmConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME) or entry.title or coordinator.userid,
            manufacturer="setlist.fm",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://www.setlist.fm/user/{quote(coordinator.userid, safe='')}",
        )
