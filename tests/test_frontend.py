"""Bundled frontend registration and retry behavior."""

import asyncio
from hashlib import sha256
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.setlistfm import async_setup
from custom_components.setlistfm.frontend import (
    ASSET,
    ASSET_URL,
    DATA_FRONTEND,
    _asset_url,
    async_register_frontend,
)


async def test_setup_loads_one_module_for_all_entries(hass: HomeAssistant) -> None:
    """Concurrent setup/reloads never duplicate paths or frontend notifications."""
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()
    changed = Mock()
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(changed, [])

    assert await async_setup(hass, {})
    await asyncio.gather(*(async_register_frontend(hass) for _ in range(4)))

    hass.http.async_register_static_paths.assert_awaited_once()
    paths = hass.http.async_register_static_paths.call_args.args[0]
    assert len(paths) == 1
    assert paths[0].url_path == ASSET_URL
    assert paths[0].path == str(ASSET)
    assert paths[0].cache_headers
    expected_url = await hass.async_add_executor_job(_asset_url)
    changed.assert_called_once_with("added", expected_url)
    assert hass.data[DATA_EXTRA_MODULE_URL].urls == {expected_url}
    assert hass.data[DATA_FRONTEND].loaded
    assert "setlistfm" not in hass.data


async def test_failed_static_registration_is_retryable(hass: HomeAssistant) -> None:
    """Do not claim the module is available when static setup fails."""
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock(side_effect=[OSError("failed"), None])
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(Mock(), [])
    with pytest.raises(OSError, match="failed"):
        await async_register_frontend(hass)
    assert hass.data[DATA_FRONTEND].url is None
    assert not hass.data[DATA_FRONTEND].loaded
    assert not hass.data[DATA_EXTRA_MODULE_URL].urls
    await async_register_frontend(hass)
    assert hass.http.async_register_static_paths.await_count == 2
    assert hass.data[DATA_FRONTEND].loaded


async def test_failed_module_registration_does_not_repeat_static_path(
    hass: HomeAssistant,
) -> None:
    """Retain successful static registration when retrying the second step."""
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()
    with patch(
        "custom_components.setlistfm.frontend.add_extra_js_url",
        side_effect=[RuntimeError("not ready"), None],
    ) as add_url:
        with pytest.raises(RuntimeError, match="not ready"):
            await async_register_frontend(hass)
        await async_register_frontend(hass)
    hass.http.async_register_static_paths.assert_awaited_once()
    assert add_url.call_count == 2
    assert hass.data[DATA_FRONTEND].loaded


def test_bundle_contents_determine_cache_key(tmp_path) -> None:
    """Changes to the asset, not a forgotten version bump, invalidate the URL."""
    bundle = tmp_path / "cards.js"
    bundle.write_bytes(b"first")
    with patch("custom_components.setlistfm.frontend.ASSET", bundle):
        first_url = _asset_url()
        assert first_url.endswith(sha256(b"first").hexdigest()[:16])
        bundle.write_bytes(b"second")
        assert _asset_url() != first_url


async def test_real_http_serves_only_bundle(hass: HomeAssistant, hass_client) -> None:
    """Exercise HA's real static-file API; integration Python is never served."""
    assert await async_setup_component(hass, "http", {})
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(Mock(), [])
    await async_register_frontend(hass)
    client = await hass_client()
    url = next(iter(hass.data[DATA_EXTRA_MODULE_URL].urls))
    response = await client.get(url)
    assert response.status == 200
    assert await response.read() == await hass.async_add_executor_job(ASSET.read_bytes)
    assert "max-age" in response.headers["Cache-Control"]
    for path in ("/setlistfm_static/__init__.py", "/setlistfm_static/manifest.json"):
        response = await client.get(path)
        assert response.status == 404
