"""Named manual scenarios; all failure semantics are test assumptions."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from .server import Account, MockSetlistApi, ResponseStep, make_concerts

SCENARIOS = (
    "baseline", "nested", "mixed", "minimal", "empty", "auth-401", "auth-403",
    "not-found", "later-404", "later-500", "rate-limit", "rate-limit-date",
    "cooldown", "transient", "timeout", "malformed-json", "malformed-schema",
    "duplicates", "changing-pagination",
)


def make_scenario(name: str, *, api_key: str = "mock-api-key") -> MockSetlistApi:
    """Create a fresh server; demo and empty are fictional usernames."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown mock scenario: {name}")
    records = make_concerts(
        0 if name == "empty" else 5,
        shape="nested" if name == "nested" else "mixed" if name == "mixed" else "flat",
        optional_fields=name != "minimal",
    )
    server = MockSetlistApi(
        [Account("demo", records), Account("empty", [])], api_key=api_key
    )
    if name in ("auth-401", "auth-403", "not-found", "later-404", "later-500"):
        status = 404 if name == "not-found" else int(name.rsplit("-", 1)[1])
        server.script(
            "demo", 2 if name.startswith("later-") else 1,
            ResponseStep(status=status), repeat_last=True,
        )
    elif name in ("rate-limit", "rate-limit-date", "cooldown"):
        retry_after = "60" if name == "cooldown" else "2"
        if name == "rate-limit-date":
            retry_after = format_datetime(
                datetime.now(timezone.utc) + timedelta(seconds=10), usegmt=True
            )
        server.script("demo", 1, ResponseStep(status=429, headers={"Retry-After": retry_after}))
    elif name == "transient":
        server.script("demo", 1, ResponseStep(status=503))
    elif name == "timeout":
        server.script("demo", 1, ResponseStep(delay=25), repeat_last=True)
    elif name == "malformed-json":
        server.script("demo", 1, ResponseStep(raw_body=b'{"setlist":'), repeat_last=True)
    elif name == "malformed-schema":
        server.script("demo", 1, ResponseStep(payload={"setlist": {}}), repeat_last=True)
    elif name in ("duplicates", "changing-pagination"):
        server.script("demo", 2, ResponseStep(payload={
            "setlist": records[:2] if name == "duplicates" else records[2:4],
            "total": 5 if name == "duplicates" else 6,
            "page": 2, "itemsPerPage": 2,
        }), repeat_last=True)
    return server
