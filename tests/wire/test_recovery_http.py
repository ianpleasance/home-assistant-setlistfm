"""Real HTTP cooldowns recover through the loaded entry's HA scheduler."""

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.setlistfm.const import CONF_API_KEY, CONF_USERID, DOMAIN
from devtools.setlistfm_mock import Account, ResponseStep, make_concerts
from tests.test_lifecycle import entity_id, load, refresh
from tests.test_rate_limit_recovery import next_delay


@pytest.fixture
async def loaded_server(hass, entry, setlist_server, recovery_clock):
    server = await setlist_server([
        Account("blabla", make_concerts(2)),
        Account("other", make_concerts(2)),
    ])
    hass.config_entries.async_update_entry(
        entry, data={CONF_USERID: "blabla", CONF_API_KEY: "mock-api-key"}
    )
    await load(hass, entry)
    await recovery_clock(2)
    return server


@pytest.mark.parametrize("delay", [60, 3600, 86400])
@pytest.mark.parametrize("trigger", ["scheduled", "manual"])
async def test_wire_rate_limit_automatically_recovers(
    hass, entry, loaded_server, recovery_clock, delay, trigger,
):
    server = loaded_server
    coordinator = entry.runtime_data
    server.script("blabla", 1, ResponseStep(status=429, headers={"Retry-After": str(delay)}))
    if trigger == "scheduled":
        await recovery_clock(21601)
    else:
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
    failed_at = hass.loop.time()
    assert [request.status for request in server.journal] == [200, 429]
    assert delay <= next_delay(hass, coordinator) <= delay + 2
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "unavailable"
    await recovery_clock(delay - 0.01)
    assert len(server.journal) == 2
    await recovery_clock(2.01)
    assert [request.status for request in server.journal] == [200, 429, 200]
    assert server.journal[-1].received_at >= failed_at + delay
    assert coordinator.last_update_success
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "2"
    assert 21599 <= next_delay(hass, coordinator) <= 21601


async def test_manual_attempt_keeps_deadline_and_success_supersedes_recovery(
    hass, entry, loaded_server, recovery_clock, freezer,
):
    server = loaded_server
    coordinator = entry.runtime_data
    server.script("blabla", 1, ResponseStep(status=429, headers={"Retry-After": "60"}))
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    first_timer = coordinator._unsub_refresh.__self__
    deadline = first_timer.when()
    await recovery_clock(20)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert len(server.journal) == 2
    assert coordinator.last_exception.retry_after == pytest.approx(40)
    assert first_timer.cancelled()
    pending_timer = coordinator._unsub_refresh.__self__
    assert pending_timer.when() == pytest.approx(deadline, abs=0.001)

    # Expiry is before HA's rounding-safe callback; the manual request wins.
    freezer.tick(40)
    await refresh(hass)
    assert pending_timer.cancelled()
    assert coordinator.last_update_success
    assert 21599 <= next_delay(hass, coordinator) <= 21601
    await recovery_clock(10)
    assert [request.status for request in server.journal] == [200, 429, 200]


async def test_same_key_extension_defers_existing_recovery_without_http(
    hass, entry, loaded_server, recovery_clock, freezer,
):
    server = loaded_server
    other = MockConfigEntry(
        domain=DOMAIN, title="Other shows", unique_id="other",
        data={CONF_USERID: "other", CONF_API_KEY: "mock-api-key"},
    )
    other.add_to_hass(hass)
    await load(hass, other)
    await recovery_clock(2)
    server.script("blabla", 1, ResponseStep(status=429, headers={"Retry-After": "60"}))
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert [request.status for request in server.journal] == [200, 200, 429]
    assert not entry.runtime_data.last_update_success
    assert not other.runtime_data.last_update_success

    freezer.tick(60)
    server.script("other", 1, ResponseStep(status=429, headers={"Retry-After": "3600"}))
    with pytest.raises(HomeAssistantError):
        await refresh(hass, {"entry_id": other.entry_id})
    extended_at = hass.loop.time()
    await recovery_clock(2)
    assert [request.status for request in server.journal] == [200, 200, 429, 429]
    assert entry.runtime_data.last_exception.retry_after == pytest.approx(3598)
    for current in (entry, other):
        assert 3598 <= next_delay(hass, current.runtime_data) <= 3600
    await recovery_clock(3597)
    assert len(server.journal) == 4
    await recovery_clock(4)
    assert [request.status for request in server.journal] == [200, 200, 429, 429, 200, 200]
    for request in server.journal[-2:]:
        assert request.received_at >= extended_at + 3600
    for current in (entry, other):
        assert current.runtime_data.last_update_success
        assert hass.states.get(entity_id(hass, current, "total_concerts")).state == "2"
        assert 21598 <= next_delay(hass, current.runtime_data) <= 21601
    await recovery_clock(10)
    assert len(server.journal) == 6
