"""Regression tests for username handling in the config flow."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from pytest_socket import socket_allow_hosts
from homeassistant import config_entries
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.setlistfm import api
from custom_components.setlistfm.config_flow import SetlistFmConfigFlow, validate_input
from custom_components.setlistfm.api import SetlistFmAuthError
from custom_components.setlistfm.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_USERID,
    DOMAIN,
)

USER_URL = "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1"
API_KEY = "CaseSensitive-API-Key"
EMPTY_ATTENDANCE = {"total": 0, "page": 1, "itemsPerPage": 20, "setlist": []}


@pytest.fixture(autouse=True)
async def settle_flow_dependencies(
    http_startup_observation, monkeypatch, hass, socket_enabled, unused_tcp_port,
):
    """Keep real flow dependencies local and finish startup before HA shuts down."""
    socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    assert await async_setup_component(hass, "http", {
        "http": {"server_host": "127.0.0.1", "server_port": unused_tcp_port},
    })
    yield
    await hass.async_block_till_done()


@pytest.fixture
def http_startup_observation():
    """Check the controlled startup probe after HA has completed its shutdown."""
    observed = []
    yield observed
    if observed:
        assert observed == ["pending", CoreState.running, "finished"]


@pytest.fixture
async def pending_http_startup(
    hass, settle_flow_dependencies, http_startup_observation, monkeypatch,
):
    """Hold real HTTP startup until HA's next task-draining boundary."""
    entered = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    original_start = hass.http.start
    original_drain = hass.async_block_till_done

    async def gated_start():
        http_startup_observation.append("pending")
        entered.set()
        await release.wait()
        http_startup_observation.append(hass.state)
        await original_start()
        http_startup_observation.append("finished")
        finished.set()

    async def release_and_drain(*args, **kwargs):
        release.set()
        await original_drain(*args, **kwargs)

    monkeypatch.setattr(hass.http, "start", gated_start)
    monkeypatch.setattr(hass, "async_block_till_done", release_and_drain)
    yield entered, finished


async def test_pending_frontend_startup_finishes_before_shutdown(
    hass, aioclient_mock, pending_http_startup,
):
    """A rejected flow can finish while its real frontend HTTP startup is pending."""
    entered, finished = pending_http_startup
    aioclient_mock.get(USER_URL, status=400)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: "blabla", CONF_API_KEY: API_KEY},
    )
    await entered.wait()
    assert result["errors"] == {"base": "invalid_response"}
    assert not finished.is_set()


@pytest.mark.parametrize("username", ["", " ", "   ", "\t", " \t\r\n "])
async def test_empty_username_rejected_before_identity_or_api(
    hass: HomeAssistant, aioclient_mock, username: str
) -> None:
    """An empty normalized username is invalid even if attendance would return 404."""
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user//attended?p=1", status=404
    )
    with (
        patch.object(SetlistFmConfigFlow, "async_set_unique_id") as set_unique_id,
        patch("custom_components.setlistfm.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERID: username, CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_username"}
    assert result["step_id"] == "user"
    set_unique_id.assert_not_called()
    assert aioclient_mock.call_count == 0
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_empty_username_can_be_corrected(hass, aioclient_mock) -> None:
    """Invalid input does not reserve an empty identity or prevent a later correction."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: " \t ", CONF_API_KEY: API_KEY},
    )
    assert result["errors"] == {"base": "invalid_username"}
    assert aioclient_mock.call_count == 0
    aioclient_mock.get(USER_URL, status=404)
    with patch("custom_components.setlistfm.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERID: " BlaBla ", CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == result["title"] == "blabla"
    assert aioclient_mock.call_count == 1


def test_invalid_username_error_is_localized() -> None:
    """The dedicated error must exist in the source strings and every locale."""
    component = Path(__file__).parents[1] / "custom_components" / DOMAIN
    translations = list((component / "translations").glob("*.json"))
    assert translations
    for path in [component / "strings.json", *translations]:
        messages = json.loads(path.read_text(encoding="utf-8"))
        assert messages["config"]["error"]["invalid_username"].strip(), path.name


@pytest.mark.parametrize("username", ["Blabla", "BLABLA", "blabla", " Blabla "])
async def test_create_entry_normalizes_username(
    hass: HomeAssistant, aioclient_mock, username: str
) -> None:
    """Use lowercase for requests and storage, not credentials or display names."""
    aioclient_mock.get(
        USER_URL,
        json=EMPTY_ATTENDANCE,
    )
    with patch("custom_components.setlistfm.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERID: username,
                CONF_API_KEY: API_KEY,
                CONF_NAME: "My Concerts",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Concerts"
    assert result["data"] == {
        CONF_USERID: "blabla",
        CONF_API_KEY: API_KEY,
        CONF_NAME: "My Concerts",
    }
    assert result["result"].unique_id == "blabla"
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][3] == {
        "x-api-key": API_KEY,
        "Accept": "application/json",
    }


@pytest.mark.parametrize("existing_username", ["blabla", "Blabla", " BLABLA "])
async def test_duplicate_username(
    hass: HomeAssistant, aioclient_mock, existing_username: str
) -> None:
    """Reject duplicates, including legacy entries, before contacting the API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=existing_username,
        data={CONF_USERID: existing_username, CONF_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: "BlaBla", CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert aioclient_mock.call_count == 0
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.unique_id == existing_username
    assert entry.data[CONF_USERID] == existing_username


async def test_different_user_can_be_added(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Normalization must not turn multi-user support into a single-entry limit."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="another-user",
        data={CONF_USERID: "another-user", CONF_API_KEY: API_KEY},
    ).add_to_hass(hass)
    aioclient_mock.get(USER_URL, json=EMPTY_ATTENDANCE)

    with patch("custom_components.setlistfm.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERID: "Blabla", CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NAME] == "blabla"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_validate_input_normalizes_username(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """The validation request also normalizes usernames when called directly."""
    data = {CONF_USERID: " Blabla ", CONF_API_KEY: API_KEY}
    aioclient_mock.get(USER_URL, json=EMPTY_ATTENDANCE)

    result = await validate_input(hass, data)

    assert result["title"] == "blabla"
    assert aioclient_mock.call_count == 1
    assert data == {CONF_USERID: " Blabla ", CONF_API_KEY: API_KEY}


@pytest.mark.parametrize(
    ("status", "error", "requests"),
    [
        (401, "invalid_auth", 1),
        (403, "invalid_auth", 1),
        (429, "rate_limited", 1),
        (500, "cannot_connect", 3),
        (400, "invalid_response", 1),
    ],
)
async def test_validation_errors_remain_visible(
    hass: HomeAssistant, aioclient_mock, status: int, error: str, requests: int
) -> None:
    """Normalizing a username must not hide API errors."""
    aioclient_mock.get(USER_URL, status=status)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: "Blabla", CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert aioclient_mock.call_count == requests


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Keep network failures visible when using Home Assistant's HTTP session."""
    aioclient_mock.get(USER_URL, exc=aiohttp.ClientConnectionError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: "Blabla", CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form(hass: HomeAssistant, aioclient_mock) -> None:
    """Opening the setup form must not contact the API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    assert aioclient_mock.call_count == 0


async def test_not_found_allows_empty_account(hass, aioclient_mock) -> None:
    """A 404 is not proof that a username is invalid."""
    aioclient_mock.get(USER_URL, status=404)
    with patch("custom_components.setlistfm.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERID: "Blabla", CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "blabla"


async def test_malformed_validation_response(hass, aioclient_mock) -> None:
    """A successful HTTP response must still contain a valid attendance page."""
    aioclient_mock.get(USER_URL, json={})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERID: "blabla", CONF_API_KEY: API_KEY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_response"}


@pytest.mark.parametrize("status,error", [
    (401, "invalid_auth"), (403, "invalid_auth"), (500, "cannot_connect"),
    (429, "rate_limited"), (400, "invalid_response"),
])
async def test_reauth_errors(hass, entry, aioclient_mock, status, error):
    aioclient_mock.get(USER_URL, status=status)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == "Blabla"
    assert aioclient_mock.call_count == 0
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data[CONF_API_KEY] == "old-key"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


async def test_auth_failure_starts_reauth_and_preserves_identity(
    hass, entry, mock_attendance, aioclient_mock
):
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_concerts", config_entry=entry,
        suggested_object_id="concerts_customized",
    )
    hass.config_entries.async_update_entry(
        entry, options={"refresh_period": 12, "number_of_concerts": 2}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_before = registry.async_get(existing.entity_id)
    original_data = dict(entry.data)
    original_options = dict(entry.options)
    old_coordinator = entry.runtime_data
    mock_attendance.side_effect = SetlistFmAuthError("rejected")
    with pytest.raises(HomeAssistantError):
        await entry.runtime_data.async_manual_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    form = await hass.config_entries.flow.async_configure(flows[0]["flow_id"])
    assert form["step_id"] == "reauth_confirm"

    mock_attendance.side_effect = None
    aioclient_mock.get(USER_URL, json=EMPTY_ATTENDANCE)
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_API_KEY: "New-CaseSensitive-Key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == {**original_data, CONF_API_KEY: "New-CaseSensitive-Key"}
    assert entry.options == original_options
    assert entry.title == "My shows"
    assert entry.unique_id == "Blabla"
    assert entry.runtime_data is not old_coordinator
    assert old_coordinator._shutdown_requested
    assert entry.runtime_data.client is not old_coordinator.client
    entity_after = registry.async_get(existing.entity_id)
    assert entity_after.id == entity_before.id
    assert entity_after.device_id == entity_before.device_id
    assert hass.states.get(existing.entity_id).state == "2"
    assert aioclient_mock.mock_calls[0][3]["x-api-key"] == "New-CaseSensitive-Key"


@pytest.mark.parametrize("source", [config_entries.SOURCE_USER, config_entries.SOURCE_REAUTH])
async def test_api_key_forms_are_masked(hass, entry, source):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": entry.entry_id},
        data=entry.data if source == config_entries.SOURCE_REAUTH else None,
    )
    schema = result["data_schema"].schema
    selector = next(value for key, value in schema.items() if key.schema == CONF_API_KEY)
    assert selector.config["type"] == "password"
    assert "old-key" not in str(result["data_schema"])


async def test_initial_auth_failure_starts_reauth(hass, entry, mock_attendance):
    mock_attendance.side_effect = SetlistFmAuthError("rejected")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_validation_cooldown_survives_client_recreation(hass, aioclient_mock):
    """Repeated validation must retain the same API key's Retry-After deadline."""
    aioclient_mock.get(USER_URL, status=429, headers={"Retry-After": "3600"})
    data = {CONF_USERID: "blabla", CONF_API_KEY: API_KEY}
    for _ in range(2):
        with pytest.raises(api.SetlistFmRateLimitError) as error:
            await validate_input(hass, data)
        assert error.value.retry_after == 3600
    assert aioclient_mock.call_count == 1
    await api.sleep(3600)
    with pytest.raises(api.SetlistFmRateLimitError):
        await validate_input(hass, data)
    assert aioclient_mock.call_count == 2


async def test_flow_resubmission_retains_cooldown(hass, aioclient_mock):
    """Submitting the form again must not bypass an upstream quota deadline."""
    aioclient_mock.get(USER_URL, status=429, headers={"Retry-After": "3600"})
    data = {CONF_USERID: "blabla", CONF_API_KEY: API_KEY}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=data
    )
    assert result["errors"] == {"base": "rate_limited"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "rate_limited"}
    assert aioclient_mock.call_count == 1
    assert hass.config_entries.async_entries(DOMAIN) == []
