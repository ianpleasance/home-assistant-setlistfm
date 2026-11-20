"""Register the bundled cards without modifying Lovelace resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

ASSET = Path(__file__).parent / "www" / "setlistfm-cards.js"
ASSET_URL = "/setlistfm_static/setlistfm-cards.js"


@dataclass
class FrontendRegistration:
    """Retain registration across entry unloads and failed setup retries."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    url: str | None = None
    loaded: bool = False


DATA_FRONTEND: HassKey[FrontendRegistration] = HassKey("setlistfm_frontend")


def _asset_url() -> str:
    """Change the module URL whenever the shipped contents change."""
    return f"{ASSET_URL}?v={sha256(ASSET.read_bytes()).hexdigest()[:16]}"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve only the JS bundle, once per HA instance, not once per account."""
    registration = hass.data.setdefault(DATA_FRONTEND, FrontendRegistration())
    async with registration.lock:
        if registration.loaded:
            return
        if registration.url is None:
            url = await hass.async_add_executor_job(_asset_url)
            await hass.http.async_register_static_paths(
                [StaticPathConfig(ASSET_URL, str(ASSET), True)]
            )
            registration.url = url
        add_extra_js_url(hass, registration.url)
        registration.loaded = True
