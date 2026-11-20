"""Opt-in real HA picker smoke host; pair with tests/frontend/live-smoke.js."""

import asyncio
from datetime import timedelta
from importlib.metadata import version
import json
import os
from pathlib import Path

import pytest
from pytest_socket import socket_allow_hosts
from homeassistant.components import websocket_api
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.setlistfm import api
from custom_components.setlistfm.const import CONF_API_KEY, CONF_NAME, CONF_USERID, DOMAIN
from devtools.setlistfm_mock import Account, MockSetlistApi, make_concerts

pytestmark = pytest.mark.skipif(
    not os.environ.get("SETLISTFM_LIVE_DIR"),
    reason="Opt-in browser smoke; see CARDS.md",
)


@pytest.fixture
def mock_recorder_before_hass(async_test_recorder):
    """Initialize recorder test patches before the HA fixture is constructed."""


@pytest.fixture(autouse=True)
def loopback_only(socket_enabled):
    """Keep all real backend transport local, including accidental requests."""
    socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)


@pytest.fixture
async def live_api(monkeypatch):
    """Run the actual API client against two fictional, isolated accounts."""
    today = dt_util.as_local(dt_util.utcnow()).date()
    concerts = make_concerts(3, shape="mixed")
    for concert, days, artist in zip(
        concerts, (2, -1, -1),
        ("Future Fixture Band", "Recent Fixture Band", "Support Fixture Band"), strict=True
    ):
        concert["eventDate"] = (today + timedelta(days=days)).strftime("%d-%m-%Y")
        concert["artist"]["name"] = artist
        concert["venue"]["id"] = "fixture-venue"
        concert["url"] = f"https://www.setlist.fm/setlist/{concert['id']}.html"
    invalid = make_concerts(1, prefix="invalid")[0]
    invalid["eventDate"] = "31-02-2026"
    concerts.append(invalid)
    async with MockSetlistApi(
        [Account("alex", concerts, items_per_page=2), Account("sam", [])]
    ) as server:
        monkeypatch.setattr(api, "BASE_URL", server.base_url)
        yield server


async def test_live_picker(
    recorder_mock,
    hass,
    hass_client,
    hass_access_token,
    live_api,
    unused_tcp_port,
):
    """Run the real frontend on loopback, with no default_config or live API."""
    from homeassistant.components.energy.websocket_api import ws_get_prefs

    ha_version = version("homeassistant")
    modern = tuple(map(int, ha_version.split(".")[:2])) >= (2026, 9)
    artifacts = Path(os.environ["SETLISTFM_LIVE_DIR"])
    await hass.async_add_executor_job(artifacts.mkdir, 0o700, True, True)
    host_path = artifacts / "live-host.json"
    result_path = artifacts / "live-result.json"
    await hass.async_add_executor_job(result_path.unlink, True)
    hass.config.time_zone = "Europe/Amsterdam"
    hass.config.skip_pip = True
    await Store(hass, 1, "lovelace").async_save(
        {"config": {"views": [{"title": "Concerts", "path": "concerts", "cards": []}]}}
    )
    config = {"http": {"server_host": "127.0.0.1", "server_port": unused_tcp_port}}
    components = ["frontend", "lovelace", "api", "persistent_notification", "config"]
    if modern:
        components.extend(("labs", "brands"))
    for component in components:
        assert await async_setup_component(hass, component, config)
    # The card picker queries optional energy preferences even without energy.
    # Register its real read-only handler without starting energy or discovery.
    websocket_api.async_register_command(hass, ws_get_prefs)
    if "onboarding" in hass.data:
        hass.data["onboarding"].onboarded = True

    registry = er.async_get(hass)
    for userid in ("alex", "sam"):
        entry = MockConfigEntry(
            domain=DOMAIN, title=userid.title(), unique_id=userid,
            data={CONF_USERID: userid, CONF_NAME: userid.title(), CONF_API_KEY: "mock-api-key"},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_concerts")
        assert entity_id
        registry.async_update_entity(entity_id, new_entity_id=f"sensor.{userid}_renamed_concerts")
    await hass.async_block_till_done()
    alex = hass.states.get("sensor.alex_renamed_concerts")
    assert alex.state == "3"
    assert alex.attributes["complete"] is False
    assert alex.attributes["skipped_count"] == 1
    assert alex.attributes["fetched_count"] == 3
    assert alex.attributes["total_attended"] == 4
    assert alex.attributes["last_update_success"] is True
    assert alex.attributes["completeness_reason"] == "invalid_records"
    assert len(alex.attributes["concerts"]) == 3
    assert len(alex.attributes["concert_visits"]) == 2
    assert alex.attributes["grouping_complete"] is False
    assert alex.attributes["concert_visits"][1]["performance_count"] == 2
    assert hass.states.get("sensor.sam_renamed_concerts").state == "0"
    client = await hass_client()
    url = str(client.make_url("/"))
    assert client.host == "127.0.0.1"
    try:
        await hass.async_add_executor_job(
            host_path.write_text,
            json.dumps({
                "url": url, "access_token": hass_access_token,
                "ha_version": ha_version, "modern": modern,
            }),
        )
        print("Local HA picker ready; run npm run test:ha with the same SETLISTFM_LIVE_DIR.", flush=True)
        async with asyncio.timeout(300):
            while not await hass.async_add_executor_job(result_path.exists):
                await asyncio.sleep(0.25)
        result = json.loads(await hass.async_add_executor_job(result_path.read_text))
        assert result["ok"], result
        assert result["errors"] == []
        lovelace = hass.data["lovelace"]
        dashboards = lovelace.dashboards if modern else lovelace["dashboards"]
        dashboard = dashboards.get("lovelace", dashboards[None])
        storage_key = f"lovelace.{dashboard.config['id']}" if dashboard.config else "lovelace"
        saved = await Store(hass, 1, storage_key).async_load()
        card = saved["config"]["views"][0]["cards"][0]
        assert card["type"] == "custom:setlistfm-complete-card"
        assert card["entity"] == "sensor.alex_renamed_concerts"
        assert card["title"] == "My live music"
        assert card["filter"] == "past"
        assert card["limit"] == 3
        assert card["show_songs"] is False
        assert card["group_by_visit"] is True
        assert len(live_api.journal) == 3
        assert all(request.status == 200 and request.api_key_matches for request in live_api.journal)
        assert live_api.counts[("alex", 1)] == live_api.counts[("alex", 2)] == 1
        assert live_api.counts[("sam", 1)] == 1
    finally:
        await hass.async_add_executor_job(host_path.unlink, True)
