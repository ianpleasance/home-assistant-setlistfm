"""Test server behavior against the derived contract without using the client."""

import asyncio

import aiohttp
import pytest

from devtools.setlistfm_mock import Account, MockSetlistApi, ResponseStep, make_concerts
from devtools.setlistfm_mock.scenarios import SCENARIOS, make_scenario

from .contract import assert_attendance_contract

HEADERS = {"x-api-key": "mock-api-key", "Accept": "application/json"}


@pytest.mark.parametrize("shape", ["flat", "nested", "mixed"])
async def test_independent_paginated_contract(setlist_server, http_session, shape):
    server = await setlist_server([Account("demo", make_concerts(shape=shape))])
    ids = []
    for page, expected_count in ((1, 2), (2, 2), (3, 1), (4, 0)):
        async with http_session.get(
            f"{server.base_url}/user/demo/attended",
            params={"p": page}, headers=HEADERS,
        ) as response:
            assert response.status == 200
            assert response.content_type == "application/json"
            payload = await response.json()
        assert_attendance_contract(payload, historical=shape != "flat")
        assert payload["page"] == page
        assert payload["total"] == 5
        assert payload["itemsPerPage"] == 2
        assert len(payload["setlist"]) == expected_count
        for record in payload["setlist"]:
            assert record["artist"]["name"] == "The Synthetic Satellites"
            sets = record.get("set", record.get("sets", {}).get("set"))
            assert [song["name"] for item in sets for song in item["song"]] == [
                "Paper Orbit", "Velvet Signal", "Clockwork Aurora",
            ]
            ids.append(record["id"])
    assert ids == ["mock-0", "mock-1", "mock-2", "mock-3", "mock-4"]
    assert len(server.journal) == 4
    for entry in server.journal:
        assert entry.method == "GET"
        assert entry.headers["x-api-key"] == "<redacted>"
        assert entry.api_key_matches
        assert entry.headers["accept"] == "application/json"
        assert entry.status == 200
        assert entry.received_at <= entry.finished_at


async def test_empty_minimal_and_multiple_accounts(setlist_server, http_session):
    server = await setlist_server([
        Account("empty", []),
        Account("minimal", make_concerts(1, optional_fields=False)),
        Account("separate", make_concerts(3, prefix="separate"), items_per_page=3),
    ])
    for userid, total in (("empty", 0), ("minimal", 1), ("separate", 3)):
        async with http_session.get(
            f"{server.base_url}/user/{userid}/attended", headers=HEADERS,
        ) as response:
            payload = await response.json()
        assert_attendance_contract(payload)
        assert payload["page"] == 1
        assert payload["total"] == total
        if userid == "minimal":
            assert payload["setlist"] == [{"id": "mock-0", "eventDate": "01-01-2026"}]


@pytest.mark.parametrize(
    ("method", "path", "headers", "status"),
    [
        ("GET", "/user/demo/attended", {"Accept": "application/json"}, 401),
        ("GET", "/user/demo/attended", {**HEADERS, "x-api-key": "mock-wrong"}, 401),
        ("GET", "/user/demo/attended", {**HEADERS, "Accept": "application/xml"}, 406),
        ("GET", "/user/demo/attended", {"x-api-key": "mock-api-key"}, 406),
        ("GET", "/user/demo/attended?p=0", HEADERS, 400),
        ("GET", "/user/demo/attended?p=-1", HEADERS, 400),
        ("GET", "/user/demo/attended?p=abc", HEADERS, 400),
        ("GET", "/user/demo/attended?p=1.5", HEADERS, 400),
        ("GET", "/user/demo/attended?p=1&p=2", HEADERS, 400),
        ("GET", "/user/demo/attended?other=1", HEADERS, 400),
        ("GET", "/user/DEMO/attended", HEADERS, 404),
        ("GET", "/user/unknown/attended", HEADERS, 404),
        ("GET", "/user/demo", HEADERS, 404),
        ("POST", "/user/demo/attended", HEADERS, 405),
    ],
)
async def test_request_contract_and_modeled_rejections(
    setlist_server, http_session, method, path, headers, status,
):
    server = await setlist_server()
    async with http_session.request(
        method, server.base_url + path, headers=headers,
    ) as response:
        assert response.status == status
        await response.read()
    assert len(server.journal) == 1
    assert server.journal[0].status == status


async def test_deprecated_profile_cannot_prove_existence(setlist_server, http_session):
    server = await setlist_server([], deprecated_profile=True)
    async with http_session.get(
        f"{server.base_url}/user/nonexistent", headers=HEADERS,
    ) as response:
        assert response.status == 200
        assert await response.json() == {"userId": "nonexistent"}
    async with http_session.get(
        f"{server.base_url}/user/nonexistent/attended", headers=HEADERS,
    ) as response:
        assert response.status == 404


async def test_configurable_matching_and_redacted_headers(setlist_server, http_session):
    server = await setlist_server(lowercase_only=False)
    async with http_session.get(
        f"{server.base_url}/user/DEMO/attended",
        headers={**HEADERS, "Authorization": "not-a-real-secret", "Cookie": "dummy=value"},
    ) as response:
        assert response.status == 200
    async with http_session.get(
        f"{server.base_url}/user/demo/attended",
        headers={**HEADERS, "x-api-key": "not-a-real-key"},
    ) as response:
        assert response.status == 401
    assert server.journal[0].headers["authorization"] == "<redacted>"
    assert server.journal[0].headers["cookie"] == "<redacted>"
    assert server.journal[1].headers["x-api-key"] == "<redacted>"
    assert server.journal[0].api_key_matches
    assert not server.journal[1].api_key_matches


@pytest.mark.parametrize("credential_header", ["X-Auth-Token", "Authorization", "User-Agent"])
async def test_rejected_request_journal_only_keeps_safe_values(
    setlist_server, http_session, credential_header,
):
    server = await setlist_server()
    header_secret = "synthetic-header-credential"
    query_secret = "synthetic/query credential"
    async with http_session.get(
        f"{server.base_url}/user/demo/attended",
        headers={**HEADERS, credential_header: header_secret},
        params=[("p", "1"), ("p", "2"), ("api_key", query_secret)],
    ) as response:
        assert response.status == 400
        await response.read()
    entry = server.journal[0]
    assert entry.headers[credential_header.lower()] == "<redacted>"
    assert entry.headers["accept"] == "application/json"
    assert entry.headers["x-api-key"] == "<redacted>"
    assert entry.api_key_matches
    assert entry.query == (("p", "1"), ("p", "2"), ("api_key", "<redacted>"))
    assert entry.path == entry.raw_path == "/rest/1.0/user/demo/attended"
    assert entry.status == 400
    assert not server.counts
    assert header_secret not in repr(server.journal)
    assert query_secret not in repr(server.journal)


@pytest.mark.parametrize("rejected", [False, True])
async def test_configured_api_key_is_never_journaled(
    setlist_server, http_session, rejected,
):
    secret = "mock-configured-sensitive-key"
    server = await setlist_server(api_key=secret)
    async with http_session.get(
        f"{server.base_url}/user/demo/attended",
        headers={**HEADERS, "x-api-key": secret},
        params={"api_key": secret} if rejected else {"p": "1"},
    ) as response:
        assert response.status == (400 if rejected else 200)
        await response.read()
    entry = server.journal[0]
    assert entry.api_key_matches
    assert entry.headers["x-api-key"] == "<redacted>"
    assert secret not in repr(server.journal)
    assert secret not in entry.raw_path


@pytest.mark.parametrize("page", ["synthetic-page-credential", "0", "-1", "1.5", "1234567890"])
async def test_journal_redacts_invalid_page_values(setlist_server, http_session, page):
    server = await setlist_server()
    async with http_session.get(
        f"{server.base_url}/user/demo/attended", headers=HEADERS, params={"p": page},
    ) as response:
        assert response.status == 400
        await response.read()
    entry = server.journal[0]
    assert entry.query == (("p", "<redacted>"),)
    assert entry.raw_path == "/rest/1.0/user/demo/attended"
    assert "synthetic-page-credential" not in repr(server.journal)


async def test_journal_redacts_unrecognized_accept_value(setlist_server, http_session):
    server = await setlist_server()
    secret = "synthetic-accept-credential"
    async with http_session.get(
        f"{server.base_url}/user/demo/attended", headers={**HEADERS, "Accept": secret},
    ) as response:
        assert response.status == 406
        await response.read()
    assert server.journal[0].headers["accept"] == "<redacted>"
    assert secret not in repr(server.journal)


async def test_independent_datasets_scripts_and_journals(setlist_server, http_session):
    account = Account("demo")
    first = await setlist_server([account])
    second = await setlist_server([account])
    first.accounts["demo"].concerts.clear()
    account.concerts.clear()
    first.script("demo", 1, ResponseStep(status=403))
    for server, status, total in ((first, 403, None), (first, 200, 0), (second, 200, 5)):
        async with http_session.get(
            f"{server.base_url}/user/demo/attended", headers=HEADERS,
        ) as response:
            assert response.status == status
            payload = await response.json()
            assert payload.get("total") == total
    assert first.counts[("demo", 1)] == 2
    assert second.counts[("demo", 1)] == 1
    assert len(first.journal) == 2
    assert len(second.journal) == 1


async def test_delayed_response_and_loopback_cleanup(http_session):
    server = MockSetlistApi([Account("demo")])
    async with server:
        url = f"{server.base_url}/user/demo/attended"
        server.script("demo", 1, ResponseStep(delay=0.01))
        async with http_session.get(url, headers=HEADERS) as response:
            assert response.status == 200
            await response.read()
        entry = server.journal[0]
        assert entry.finished_at - entry.received_at >= 0.01
        assert server.base_url.startswith("http://127.0.0.1:")
    with pytest.raises(aiohttp.ClientConnectionError):
        await http_session.get(url, headers=HEADERS)
    with pytest.raises(RuntimeError, match="Start the server"):
        _ = server.base_url


async def test_cleanup_cancels_gated_handlers(http_session):
    server = MockSetlistApi([Account("demo")])
    async with server:
        server.script("demo", 1, ResponseStep(gate=asyncio.Event()))
        task = asyncio.create_task(
            http_session.get(f"{server.base_url}/user/demo/attended", headers=HEADERS)
        )
        await server.wait_for_requests(1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert server.journal[0].cancelled
    assert server.journal[0].finished_at is not None


@pytest.mark.parametrize("name", SCENARIOS)
async def test_manual_scenarios_are_fresh_and_runnable(name, http_session):
    first = make_scenario(name)
    second = make_scenario(name)
    assert first is not second
    if name == "timeout":
        # Verify this long manual scenario with a short real transport timeout.
        timeout = aiohttp.ClientTimeout(total=0.05)
    else:
        timeout = aiohttp.ClientTimeout(total=2)
    async with first:
        url = f"{first.base_url}/user/demo/attended"
        if name == "timeout":
            with pytest.raises(TimeoutError):
                await http_session.get(url, headers=HEADERS, timeout=timeout)
        else:
            async with http_session.get(url, headers=HEADERS, timeout=timeout) as response:
                assert response.status == {
                    "auth-401": 401, "auth-403": 403, "not-found": 404,
                    "rate-limit": 429, "rate-limit-date": 429, "cooldown": 429,
                    "transient": 503,
                }.get(name, 200)
                if name == "malformed-json":
                    assert await response.read() == b'{"setlist":'
                else:
                    payload = await response.json() if response.status != 404 else None
                    if name == "malformed-schema":
                        assert payload == {"setlist": {}}
                    elif response.status == 200:
                        assert_attendance_contract(payload, historical=name in ("mixed", "nested"))
                        assert payload["total"] == (0 if name == "empty" else 5)
                if name in ("rate-limit", "rate-limit-date", "cooldown"):
                    assert "Retry-After" in response.headers
        assert len(first.journal) == 1
        assert not second.journal
        if name in ("later-404", "later-500", "duplicates", "changing-pagination"):
            async with http_session.get(url, params={"p": 2}, headers=HEADERS) as response:
                assert response.status == {"later-404": 404, "later-500": 500}.get(name, 200)
                if response.status == 200:
                    payload = await response.json()
                    assert payload["page"] == 2
                    if name == "duplicates":
                        assert [record["id"] for record in payload["setlist"]] == [
                            "mock-0", "mock-1",
                        ]
                    else:
                        assert payload["total"] == 6


@pytest.mark.parametrize(
    "payload",
    [
        {"setlist": [], "page": 1, "total": "0", "itemsPerPage": 2},
        {"setlist": {}, "page": 1, "total": 0, "itemsPerPage": 2},
        {"setlist": [{"id": "x", "eventDate": "01-01-2026", "set": {}}],
         "page": 1, "total": 1, "itemsPerPage": 2},
    ],
)
def test_independent_contract_checker_rejects_bad_shapes(payload):
    with pytest.raises(AssertionError):
        assert_attendance_contract(payload)
