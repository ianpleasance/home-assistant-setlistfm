# Local setlist.fm mock API

This is **test/development infrastructure**, not a production proxy or a complete
API clone. It uses aiohttp, synthetic accounts, fictional artists/songs/locations,
and inert `.invalid` attribution URLs. It never contacts setlist.fm, loads a Home
Assistant configuration, or fetches external assets. No live key is needed.

## Manual use

Use the repository's test environment (Linux/WSL, Python 3.14):

```console
python -m pip install -r requirements-test.txt
python -m devtools.setlistfm_mock --scenario mixed --port 8765 --api-key mock-api-key
```

The command stays in the foreground, binds **127.0.0.1 only**, and shuts down with
Ctrl+C. There is no reload watcher, public-host option, admin endpoint or persistent
state. Restarting resets scripts and datasets. Only dummy keys prefixed `mock-` are
accepted by the constructor/CLI; use no real credentials in requests.

From another terminal:

```console
curl -H "Accept: application/json" -H "x-api-key: mock-api-key" "http://127.0.0.1:8765/rest/1.0/user/demo/attended?p=1"
```

`demo` has five concerts over three pages (two items per page); `empty` has none.
The `empty` scenario also clears `demo`. The API is JSON-only. For standalone use,
aiohttp is the only runtime import beyond the standard library; these tools are
not packaged with `custom_components/setlistfm` and change no normal HA install
requirements.

The production client URL remains exactly `https://api.setlist.fm/rest/1.0`.
There is **no user-configurable production endpoint**. An isolated test or demo
harness can temporarily patch `custom_components.setlistfm.api.BASE_URL` to the
local server's API root **before constructing the client/coordinator**. Do not
redirect a real user's HA instance or install their configuration for testing.

## Reuse in tests

`tests/wire/conftest.py` supplies `setlist_server`, an async factory owning all
servers it starts, and `http_session`, an actual aiohttp client session. The
factory patches only the existing `api.BASE_URL` constant; patches, sockets,
sessions, outstanding handlers and per-server state are cleaned up at teardown.
The tests permit socket connections only to `127.0.0.1` (plus local Unix sockets
needed by the event loop), never arbitrary internet access.

```python
from devtools.setlistfm_mock import Account, ResponseStep, make_concerts

async def test_example(setlist_server, http_session):
    server = await setlist_server([
        Account("demo", make_concerts(5, shape="nested"), items_per_page=2),
        Account("empty", []),
    ])
    server.script("demo", 2, ResponseStep(status=503))
    # The first page-2 request gets 503; the next gets the ordinary page.
```

Outside pytest, use `async with MockSetlistApi(accounts) as server` for an ephemeral
loopback port and `server.base_url`. Each instance must have a single context;
create a new instance to restart. `server.app` is also a regular aiohttp Application
for another isolated harness. Datasets are deep-copied at construction, so sharing
an Account definition does not share mutable records between server instances.
`accounts=[]` means no accounts, not the demo dataset.

`script(userid, page, *steps, repeat_last=False)` replaces a page's response script.
It runs only after valid method, path, header and query handling. Each matching
request consumes one step, then falls back to the current dataset. `repeat_last`
keeps the final fault active. Other accounts/pages are unaffected. Mutate
`server.accounts[userid].concerts` between refreshes to model changed attendance.
`ResponseStep` supports status, headers, JSON payload, raw bytes/content type,
delay in seconds, or an `asyncio.Event` gate. Gates let cancellation/timeout tests
wait for actual arrival without guessing how long a request takes. Raw `b"null"`
models JSON null; no payload means use the ordinary page or a synthetic error.

`server.journal` records method, decoded path, encoded `raw_path` **without its
query string**, sanitized query pairs (including duplicates), lowercased headers,
monotonic arrival/finish times, response status and handler cancellation. Only the
exact `Accept: application/json` header value is retained; every other header value
is `<redacted>`, including the configured API key and unexpected credential headers.
The `api_key_matches` boolean records whether the received key exactly matched the
configured key without retaining its value. Query values are retained only for `p`
containing a valid positive ASCII
integer of up to nine digits; unknown parameters and invalid `p` values are
`<redacted>`. This sanitization also applies to rejected requests. No access log is
written. `server.counts[(userid, page)]` counts attendance
requests that passed request checks, including injected failures;
`await server.wait_for_requests(n)` synchronizes on the journal's nth arrival.
Times describe the handler, not the client's completion or simulated backoff.

## Contract and provenance

Reviewed **2026-09-29**, setlist.fm API **1.0**, Swagger **2.0**. This table is a
small derived contract, not a verbatim copy or full vendored upstream schema.
Sources:

- [API documentation](https://api.setlist.fm/docs/1.0/index.html) and
  [Swagger](https://api.setlist.fm/docs/1.0/ui/swagger.json): JSON Accept negotiation,
  `x-api-key`, `/rest` base path, API version and definitions.
- [Attended resource](https://api.setlist.fm/docs/1.0/resource__1.0_user__userId__attended.html):
  `GET /rest/1.0/user/{userId}/attended`, integer query `p` defaulting to 1,
  a documented 200 response referencing `json_Setlists`.
- [Setlists](https://api.setlist.fm/docs/1.0/json_Setlists.html) and
  [Setlist](https://api.setlist.fm/docs/1.0/json_Setlist.html): fields below.
- [Deprecated user resource](https://api.setlist.fm/docs/1.0/resource__1.0_user__userId_.html):
  always returns a result even for nonexistent users. Opt-in `deprecated_profile`
  returns only `userId`; disabled by default. Wire tests prove the production
  client never requests it.
- [Public historical recording, pinned commit](https://github.com/zschumacher/setlist-fm-client/blob/2b492a6fc940a484e3e4b6461a5057111ed44004/tests/cassettes/TestGetSetlist.test%5BAccept.json0%5D.yaml#L18-L36):
  the recorded setlist response dated July 2022 has `sets.set`. This is evidence
  of a historical **setlist object** representation, not an authenticated
  attended-endpoint check today. Only the structure is reproduced; no recording,
  personal account data, real songs or credentials are copied.

| Successful subset | Types and behavior |
| --- | --- |
| Envelope | Object containing `setlist` array, `total`, `page`, `itemsPerPage` |
| Pagination | Swagger numbers; the mock uses nonnegative integer total, positive integer page/size and exact slicing of its dataset |
| Concert identity/date | Nonempty string `id`, string `eventDate` in `dd-MM-yyyy` |
| Optional artist/location | Objects `artist`, `venue`, `venue.city`, `venue.city.country`; names/mbid/state/country code are strings when present |
| Optional attribution | String `url`, always an inert `.invalid` URL in generated data |
| Published songs | Top-level `set` array; each set has a `song` array of objects with string `name`; encore is numeric |
| Historical compatibility | `sets: {"set": [...]}` only when explicitly selected; `mixed` alternates the representations between records |

The docs do not exhaustively declare required fields. Requiring identity/date,
all envelope fields, integer counts, and positive page size is our **successful
test subset**, not a claim that all other upstream responses are invalid.
`minimal` omits optional artist, venue, URL and song data to exercise graceful
handling. `tests/wire/contract.py` validates raw HTTP JSON independently: it
imports neither the generator nor the integration parser/normalizer. Negative
tests check that this independent checker rejects intentionally broken shapes.

## Explicit assumptions and fault scenarios

As of the review date above, Swagger documents only **200** for attendance.
Every error status/retry instruction below is a **modeled test scenario**, not
a claim that setlist.fm guarantees that behavior. No authenticated live checks
were performed; in particular, **no empty-vs-unknown 404 distinction or
1,000-attended-result limit has been verified**.

Baseline model choices: lowercase-only matching (configurable), unknown user 404,
empty account 200 with total 0, beyond-last-page 200 with an empty list, missing/
incorrect key 401, exact `Accept: application/json` required (otherwise 406),
and bad/duplicate/unknown query arguments 400. These choices make mistakes
visible; the server does not implement XML, general media negotiation,
localization, global quotas, quota timing, or other setlist.fm endpoints.

| `--scenario` | Behavior for `demo` |
| --- | --- |
| `baseline`, `nested`, `mixed`, `minimal`, `empty` | Ordinary dataset/representation variations |
| `auth-401`, `auth-403`, `not-found` | Persistent first-page status; 404 is deliberately ambiguous |
| `later-404`, `later-500` | Persistent page-2 failure after a valid page 1 |
| `rate-limit`, `rate-limit-date` | One first-page 429; Retry-After 2 seconds or HTTP date 10 seconds after server creation |
| `cooldown` | One first-page 429 with Retry-After 60 seconds |
| `transient` | One first-page 503, then recovery |
| `timeout` | Persistent 25-second handler delay, exceeding the real client's 20-second timeout |
| `malformed-json`, `malformed-schema` | Persistent invalid JSON bytes or wrong envelope fields |
| `duplicates`, `changing-pagination` | Repeated IDs or changed total on page 2 |

Long delays exist **only for manual scenarios**. Automated wire tests shorten
the client's real aiohttp timeout to 50 ms and use event gates; most retry/pacing
tests use the existing API clock fixture. One separate real-clock test uses real
sleep and monotonic time with a 50 ms pacing interval, checking server receipt
timestamps with 10 ms of loopback scheduling tolerance. No transport calls are
monkeypatched and no test sleeps for 20/60 seconds. Coverage includes outgoing
headers/path/pages, auth,
bounded retry/exhaustion, seconds/date Retry-After, retained cooldown, cancellation,
real malformed content, optional fields and full previous-coordinator-snapshot
retention after later failures. Existing fast unit tests remain in place.

```console
python -m pytest tests/wire -q
python -m pytest -q
```
