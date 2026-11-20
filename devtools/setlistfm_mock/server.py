"""Implement the small attendance contract documented in README.md."""

from __future__ import annotations

import asyncio
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Literal, Required, TypedDict

from aiohttp import web

DUMMY_API_KEY = "mock-api-key"
API_PATH = "/rest/1.0"


def _is_page_number(value: str) -> bool:
    return value.isascii() and value.isdigit() and len(value) <= 9 and int(value) > 0


class Concert(TypedDict, total=False):
    """Integration-relevant fields, with optional data deliberately omittable."""

    id: Required[str]
    eventDate: Required[str]
    artist: dict[str, Any]
    venue: dict[str, Any]
    url: str
    set: list[dict[str, Any]]
    sets: dict[str, list[dict[str, Any]]]


class AttendancePage(TypedDict):
    """Derived from API 1.0 json_Setlists, not the integration's parser."""

    setlist: list[Concert]
    total: int
    page: int
    itemsPerPage: int


def make_concerts(
    count: int = 5,
    *,
    prefix: str = "mock",
    shape: Literal["flat", "nested", "mixed"] = "flat",
    optional_fields: bool = True,
) -> list[Concert]:
    """Generate fictional records; .invalid URLs never load external resources."""
    if count < 0 or shape not in ("flat", "nested", "mixed"):
        raise ValueError("Choose a nonnegative count and flat, nested or mixed shape")
    records: list[Concert] = []
    for index in range(count):
        record: Concert = {
            "id": f"{prefix}-{index}",
            "eventDate": f"{index % 28 + 1:02d}-01-2026",
        }
        if optional_fields:
            record.update(
                artist={"name": "The Synthetic Satellites"},
                venue={
                    "name": "Fictional Moon Hall",
                    "city": {
                        "name": "Example Harbour",
                        "state": "Imaginary Province",
                        "country": {"code": "ZZ", "name": "Example Country"},
                    },
                },
                url=f"https://setlist.invalid/setlist/{prefix}-{index}",
            )
            sets = [
                {"song": [{"name": "Paper Orbit"}, {"name": "Velvet Signal"}]},
                {"encore": 1, "song": [{"name": "Clockwork Aurora"}]},
            ]
            if shape == "nested" or (shape == "mixed" and index % 2):
                record["sets"] = {"set": sets}
            else:
                record["set"] = sets
        records.append(record)
    return records


@dataclass
class Account:
    """A synthetic account; the server takes a private copy on construction."""

    userid: str
    concerts: list[Concert] = field(default_factory=make_concerts)
    items_per_page: int = 2

    def __post_init__(self) -> None:
        if not self.userid or self.userid != self.userid.strip().lower():
            raise ValueError("Mock account IDs must be nonempty, trimmed and lowercase")
        if type(self.items_per_page) is not int or self.items_per_page < 1:
            raise ValueError("items_per_page must be a positive integer")


@dataclass(frozen=True)
class ResponseStep:
    """Explicit fault injection; an exhausted script resumes normal responses.

    A missing payload uses the ordinary page (200) or a synthetic error body.
    Use raw_body=b"null" for a literal JSON null, or arbitrary bytes for bad JSON.
    An event gate allows deterministic cancellation/timeout tests without sleeps.
    """

    status: int = 200
    payload: dict[str, Any] | list[Any] | None = None
    raw_body: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str = "application/json"
    delay: float = 0
    gate: asyncio.Event | None = None

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError("Response delay cannot be negative")
        if self.payload is not None and self.raw_body is not None:
            raise ValueError("Choose payload or raw_body, not both")


@dataclass
class JournalEntry:
    """Received request and server timing; secrets are not retained."""

    method: str
    path: str
    raw_path: str
    query: tuple[tuple[str, str], ...]
    headers: dict[str, str]
    api_key_matches: bool
    received_at: float
    finished_at: float | None = None
    status: int | None = None
    cancelled: bool = False


@dataclass
class _Script:
    steps: deque[ResponseStep]
    repeat_last: bool

    def next(self) -> ResponseStep | None:
        if not self.steps:
            return None
        if self.repeat_last and len(self.steps) == 1:
            return self.steps[0]
        return self.steps.popleft()


class MockSetlistApi:
    """Own independent datasets, scripts, journal, and a real aiohttp application."""

    def __init__(
        self,
        accounts: Sequence[Account] = (),
        *,
        api_key: str = DUMMY_API_KEY,
        lowercase_only: bool = True,
        deprecated_profile: bool = False,
    ) -> None:
        if not api_key.startswith("mock-"):
            raise ValueError("Only dummy API keys beginning with 'mock-' are allowed")
        self.accounts = {account.userid: deepcopy(account) for account in accounts}
        if len(self.accounts) != len(accounts):
            raise ValueError("Duplicate mock account IDs")
        self.api_key = api_key
        self.lowercase_only = lowercase_only
        self.journal: list[JournalEntry] = []
        self.counts: Counter[tuple[str, int]] = Counter()
        self._scripts: dict[tuple[str, int], _Script] = {}
        self._requests_changed = asyncio.Condition()
        self._runner: web.AppRunner | None = None
        self._base_url: str | None = None
        self.app = web.Application(middlewares=[self._record_request])
        self.app.router.add_get(
            f"{API_PATH}/user/{{userid}}/attended", self._attended, allow_head=False
        )
        if deprecated_profile:
            self.app.router.add_get(
                f"{API_PATH}/user/{{userid}}", self._profile, allow_head=False
            )

    @property
    def base_url(self) -> str:
        """Return the bound API root only while the context-managed server runs."""
        if self._base_url is None:
            raise RuntimeError("Start the server with 'async with' first")
        return self._base_url

    async def __aenter__(self) -> MockSetlistApi:
        if self._runner is not None:
            raise RuntimeError("Create a fresh mock server for each context")
        self._runner = web.AppRunner(
            self.app, access_log=None, handler_cancellation=True, shutdown_timeout=0.1
        )
        await self._runner.setup()
        try:
            site = web.TCPSite(self._runner, "127.0.0.1", 0)
            await site.start()
            port = self._runner.addresses[0][1]
            self._base_url = f"http://127.0.0.1:{port}{API_PATH}"
        except BaseException:
            await self._runner.cleanup()
            raise
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._base_url = None

    def script(
        self, userid: str, page: int, *steps: ResponseStep, repeat_last: bool = False
    ) -> None:
        """Replace a page's response sequence; scripts run after request checks."""
        if page < 1 or not steps:
            raise ValueError("A script requires a positive page and at least one step")
        self._scripts[(userid, page)] = _Script(deque(steps), repeat_last)

    async def wait_for_requests(self, count: int, *, timeout: float = 2) -> None:
        """Synchronize tests with arrival, not arbitrary scheduling delays."""
        async with asyncio.timeout(timeout):
            async with self._requests_changed:
                await self._requests_changed.wait_for(lambda: len(self.journal) >= count)

    @web.middleware
    async def _record_request(
        self,
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        safe_headers = {"accept": "application/json"}
        headers = {
            key.lower(): value if safe_headers.get(key.lower()) == value else "<redacted>"
            for key, value in request.headers.items()
        }
        query = tuple(
            (key, value if key == "p" and _is_page_number(value) else "<redacted>")
            for key, value in request.query.items()
        )
        entry = JournalEntry(
            method=request.method,
            path=request.path,
            raw_path=request.rel_url.raw_path,
            query=query,
            headers=headers,
            api_key_matches=request.headers.get("x-api-key") == self.api_key,
            received_at=monotonic(),
        )
        async with self._requests_changed:
            self.journal.append(entry)
            self._requests_changed.notify_all()
        try:
            response = await handler(request)
            entry.status = response.status
            return response
        except web.HTTPException as err:
            entry.status = err.status
            raise
        except asyncio.CancelledError:
            entry.cancelled = True
            raise
        finally:
            entry.finished_at = monotonic()

    def _check_headers(self, request: web.Request) -> None:
        if request.headers.get("x-api-key") != self.api_key:
            raise web.HTTPUnauthorized(text="Mock API requires its dummy x-api-key")
        # This intentionally narrow JSON-only subset does not negotiate XML.
        if request.headers.get("Accept") != "application/json":
            raise web.HTTPNotAcceptable(text="Mock API requires Accept: application/json")

    async def _attended(self, request: web.Request) -> web.Response:
        self._check_headers(request)
        values = request.query.getall("p", ["1"])
        if (
            set(request.query) - {"p"}
            or len(values) != 1
            or not _is_page_number(values[0])
        ):
            raise web.HTTPBadRequest(text="Mock API requires a single positive integer p")
        page = int(values[0])
        userid = request.match_info["userid"]
        if not self.lowercase_only:
            userid = userid.lower()
        self.counts[(userid, page)] += 1
        script = self._scripts.get((userid, page))
        step = script.next() if script else None
        if step is not None:
            if step.gate is not None:
                await step.gate.wait()
            if step.delay:
                await asyncio.sleep(step.delay)
            if step.raw_body is not None:
                return web.Response(
                    status=step.status, body=step.raw_body,
                    headers=step.headers, content_type=step.content_type,
                )
            if step.payload is not None or step.status != 200:
                return web.json_response(
                    step.payload if step.payload is not None else {"error": "Mock scenario"},
                    status=step.status, headers=step.headers,
                )
        account = self.accounts.get(userid)
        if account is None:
            raise web.HTTPNotFound(text="Mock attendance not found (ambiguous)")
        start = (page - 1) * account.items_per_page
        payload: AttendancePage = {
            "setlist": account.concerts[start:start + account.items_per_page],
            "total": len(account.concerts),
            "page": page,
            "itemsPerPage": account.items_per_page,
        }
        return web.json_response(payload, headers=step.headers if step else None)

    async def _profile(self, request: web.Request) -> web.Response:
        self._check_headers(request)
        return web.json_response({"userId": request.match_info["userid"]})
