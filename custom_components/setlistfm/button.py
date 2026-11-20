"""Manual refresh control for each setlist.fm service device."""
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SetlistFmConfigEntry
from .entity import SetlistFmEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SetlistFmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SetlistFmRefreshButton(entry)])


class SetlistFmRefreshButton(SetlistFmEntity, ButtonEntity):
    """Retry a failed connection or refresh the current snapshot."""

    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: SetlistFmConfigEntry) -> None:
        super().__init__(entry.runtime_data, entry, "refresh")

    @property
    def available(self) -> bool:
        """Allow retries after a failed fetch while the entry remains loaded."""
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_manual_refresh()
