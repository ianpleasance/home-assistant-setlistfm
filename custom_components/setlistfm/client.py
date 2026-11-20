"""Create API clients with Home Assistant-owned quota state."""
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .api import RequestStateStore, SetlistFmClient
from .const import DOMAIN

DATA_REQUEST_STATES: HassKey[RequestStateStore] = HassKey(f"{DOMAIN}_request_states")


@callback
def async_create_client(
    hass: HomeAssistant, api_key: str, userid: str
) -> SetlistFmClient:
    """Share deadlines across flows, entries and failed-setup retries until restart."""
    states: RequestStateStore | None = hass.data.get(DATA_REQUEST_STATES)
    if states is None:
        states = hass.data[DATA_REQUEST_STATES] = RequestStateStore()
    return SetlistFmClient(
        async_get_clientsession(hass), api_key, userid, request_states=states
    )
