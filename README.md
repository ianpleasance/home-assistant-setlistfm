# Setlist.fm Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-c62828.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/ianpleasance/home-assistant-setlistfm?display_name=tag&sort=semver&color=blue&label=version)](https://github.com/ianpleasance/home-assistant-setlistfm/releases/latest)
[![license](https://img.shields.io/github/license/ianpleasance/home-assistant-setlistfm)](LICENSE)

This custom integration allows you to display your concert attendance data from [Setlist.fm](https://www.setlist.fm) in Home Assistant.

Requires **Home Assistant 2025.1.0 or newer** for typed config-entry runtime data
and an explicit coordinator/config-entry relationship. Upgrades retain existing
Concerts entity IDs, custom names, options and device associations.

## Features

- ✅ **UI Configuration** - No YAML required! Configure through the Home Assistant UI
- ✅ **Async/Await** - Non-blocking API calls that won't freeze your Home Assistant
- ✅ **Multiple Users** - Add multiple Setlist.fm accounts
- ✅ **Flexible Filtering** - Show past concerts, upcoming concerts, or all
- ✅ **Customizable Display** - Choose date format and number of concerts to display
- ✅ **Automatic Updates** - Configurable refresh interval (1-24 hours)
- ✅ **Rate Limiting Protection** - Built-in retry logic for API rate limits
- ✅ **Proper Entity Registry** - Entities have unique IDs for proper HA integration
- ✅ **Bundled Community Cards** - Complete, Compact, Deluxe and Mobile cards with previews and a visual account selector; no dashboard YAML or manual JS resources
- ✅ **Native Overview** - Five sensors and a Refresh button per account, grouped under its service device
- ✅ **Unique Concert Visits** - Count venue-days across the fetched history and optionally group card lineups without losing individual setlists
- ✅ **Reauthentication** - Replace a rejected API key without recreating the account or its entities

## Installation

### HACS (Recommended)

With HACS already installed, open the upstream repository in your Home Assistant instance:

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ianpleasance&repository=home-assistant-setlistfm&category=integration)

My Home Assistant asks for your instance URL the first time. The button opens
the repository in HACS; you still confirm installation there.

If the link does not work, follow the manual
[custom repository steps](https://www.hacs.xyz/docs/faq/custom_repositories/):

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add `https://github.com/ianpleasance/home-assistant-setlistfm` as an integration repository
5. Click "Install" on the Setlist.fm card
6. Restart Home Assistant

**Testing a fork:** add that fork's own GitHub URL as a custom integration
repository instead. The badge and project links above intentionally point to
the original upstream repository, not a contributor's fork.

### Manual Installation

1. Download the version you want to install and copy `custom_components/setlistfm` to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Getting Your Setlist.fm Credentials

1. **Username**:
   - Go to your Setlist.fm profile
   - Use the part after `/user/` in `https://www.setlist.fm/user/YOUR_USERNAME`, not the full URL or your display name
   - You can also find your username at the top right, next to **Add setlist**
   - Usernames are automatically converted to lowercase and surrounding spaces are removed, so `Blabla` becomes `blabla`

2. **API Key**:
   - Go to https://www.setlist.fm/settings/api
   - Request an API key (it's free!)
   - Copy the API key once approved

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Setlist.fm"
4. Enter your Username and API Key
5. (Optional) Enter a friendly name
6. Click **Submit**

Empty or whitespace-only usernames are rejected before any API request.
Setup checks access to the supported attended-concert endpoint, not account existence.
The entry title uses your optional friendly name, otherwise your normalized username;
the integration no longer requests a profile display name. See [API behavior and
coverage](#api-behavior-and-coverage) for empty-account and username-validation limits.

### Configuring Options

After adding the integration, you can configure options:

1. Go to **Settings** → **Devices & Services**
2. Find your Setlist.fm integration
3. Click **Configure**
4. Adjust the following options:
   - **Refresh Period**: How often to check for updates (1-24 hours, default: 6)
   - **Number of Concerts**: Maximum individual performances in the legacy list and, independently, maximum visits in the grouped list (1-50, default: 10)
   - **Date Format**: Choose your preferred date format
     - `DD-MM-YYYY` (31-12-2024)
     - `DD-MM-YY` (31-12-24)
     - `MM-DD-YYYY` (12-31-2024)
     - `MM-DD-YY` (12-31-24)
   - **Show Concerts**: Filter which concerts to display
     - `All concerts` - Show both past and upcoming
     - `Upcoming only` - Only show future concerts
     - `Past only` - Only show attended concerts

## Entities Created

Each user gets one service device, linked to their setlist.fm profile, with five
sensors and one button. Open it through **Settings → Devices & Services →
setlist.fm → your device**. These are standard Home Assistant entities, usable
with the visual dashboard card/entity picker; no replacement device screen is needed.

| Entity | Meaning |
| --- | --- |
| Concerts shown | Individual performance/setlist count after your date filter and display limit; retains the existing unique ID and attributes |
| Total concerts | Authoritative API artist-performance/setlist total before filtering, not unique visits; **unknown** when not supplied |
| Unique concert visits | Distinct venue-days across the full fetched, validated snapshot; **unknown** when coverage or grouping is incomplete |
| Next concert | Date of the earliest returned setlist on/after today, with `artist`, `venue`, `url`, `complete` and `completeness_reason` attributes |
| Last successful update | Diagnostic timestamp of the last completed retrieval, with `last_update_success` and an optional `last_error` |
| Refresh | Configuration button; waits for a real refresh and reports failures, also usable to retry a failed connection |

The Concerts shown sensor (previously named Concerts) retains `concerts`, `concert_list`, `last_updated`,
`last_update_success`, optional `last_error`, and the [coverage attributes](#coverage-metadata).
Its displayed count is not a measurement or a monotonically increasing counter,
so it no longer advertises a long-term-statistics state class.
For example, **Total concerts: 45** and **Concerts shown: 10** are expected when
the display limit is 10. Only the default label changes; existing entity IDs,
unique IDs and user-assigned names are preserved.

Next concert uses the **full fetched dataset**, not the display filter or limit.
No matching setlist gives **unknown**, not a claim that you have no future bookings.
Dates and display filters re-evaluate at local midnight without an API request.
All five sensors become **unavailable** on a failed retrieval; the previous
snapshot and successful timestamp remain in memory until recovery. A restart or
entry reload begins with no timestamp until the first successful retrieval.

`last_updated` and Last successful update share one timezone-aware timestamp.
Reading attributes never changes it. A failed later page does not advance it.
A completed retrieval can still have `complete: false` (ambiguous first-page
404 or skipped records): the timestamp means the fetch completed, **not** that
the attendance history is complete.

**Entity IDs are generated by Home Assistant from device/entity names and may
be customized; they do not inherently start with `sensor.setlistfm_`.** Find the
actual IDs in entity settings. All example IDs below are placeholders; replace
each full ID, rather than just substituting your username. Existing registered
Concerts IDs are preserved.

### Unique concert visits

**Unique concert visits** is a normal count sensor with the
`mdi:calendar-check-outline` icon, not a lifetime-increasing counter. It groups
performances by the tuple **(canonical `DD-MM-YYYY` event date, valid nonempty
string `venue.id`)**. Opening acts and another artist at the same venue on the
same date count as one visit. This is a venue-day rule, not event identification:
two independent shows at that venue on the same day also collapse, while festival
stages with different venue IDs remain separate. Venue names are never used to
guess identity, and no headliner or billing order is inferred.

The count uses **all fetched pages**, before date filtering or display limits,
with no extra API requests. A metadata-confirmed empty history gives **0**.
Incomplete coverage, an ambiguous first-page 404, invalid dates or missing venue
identity give **unknown**, not a guessed total. Valid performances without venue
identity remain separate in the grouped display with an uncertain-grouping
warning; they are not discarded or merged by name. Grouping metadata exposes the
identified count even when the overall total is unknown.

**Concerts shown** and **Total concerts** keep their existing performance-count
meanings. For example, three artists on the same date at the same venue contribute
three setlists to Total concerts but one Unique concert visit. Turning on grouped
cards does not change either existing sensor's value.

### Shared API fetching

All five sensors read the **same cached coordinator snapshot per account**; they
do not poll setlist.fm separately. One scheduled or manual refresh fetches the
attendance dataset once, then updates every sensor locally. The Refresh button
uses that same coordinator.

A single-page account needs **one HTTP request per refresh**, not five. A
three-page history needs three requests, not fifteen: pagination is required to
avoid silently dropping concerts. Reading attributes, midnight date updates and
rendering/configuring the bundled cards do not make extra setlist.fm requests.
Setup and reauthentication perform their own access-validation check.

## Services

### `setlistfm.refresh`

Refresh concert data and wait for the result. The per-user Refresh button is
usually easier than supplying an entry ID. Requests remain subject to API pacing
and cooldowns; repeated or concurrent actions are serialized with scheduled polls.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | No | A loaded setlist.fm entry; omission refreshes all loaded entries. |

Use the entry picker in **Developer Tools → Actions → setlistfm.refresh**.
An empty, unknown, foreign or unloaded explicit ID is rejected, never interpreted
as "all". No loaded entries is an error. All-target refresh attempts every loaded
entry and reports any failures. The action remains registered across entry unloads
and setup failures.

**Example — refresh a specific entry**:
```yaml
service: setlistfm.refresh
data:
  entry_id: abc123def456abc123def456abc123de
```

**Example — refresh all entries**:
```yaml
service: setlistfm.refresh
```

**Example automation**:
```yaml
automation:
  - alias: "Refresh Setlist.fm Daily"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: setlistfm.refresh
```

## Usage Examples

### Community cards (no YAML)

Edit a dashboard and choose **Add card > By cards > Community**, then search for **setlist.fm**. Choose **Complete**, **Compact**, **Deluxe** or **Mobile** and select your account's concerts entity in the visual editor. The integration automatically loads these cards after installation and a Home Assistant restart.

Some versions label the tab **By card**. Home Assistant 2025.1 lists the presets
as **Custom: setlist.fm Complete** (and the other names), without the newer
Community grouping. The same visual editor and account selection work there.

These are individual cards, not full dashboard views. They support multiple accounts, renamed entities, HA themes and mobile layouts. They show the integration's filtered and capped display list, not your complete attendance history. See [CARDS.md](CARDS.md) for options, update behavior and limitations.

All four presets offer **Group by concert visit**, off by default
(`group_by_visit: false`). Enable it to show each venue-day's artists
alphabetically with individual safe setlist links and song counts. Grouping
happens in the integration before filtering and limiting, not approximately in
the browser. The legacy list stays available for existing dashboards.

The cards' **Next in this list** highlight uses the available display records;
the native **Next concert** sensor uses the full fetched dataset. They can differ
when integration filters or limits omit a concert. Cards distinguish loading,
unavailable, failed-refresh and incomplete-data states, including invalid
records already skipped by the backend. Reload open browser/Companion App views
after an integration upgrade to load the content-versioned bundle.

### Display in Lovelace

The following YAML examples remain an optional alternative.

**Simple Markdown Card**:
```yaml
type: markdown
content: |
  ## 🎵 My Concerts
  {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

**Entities Card**:
```yaml
type: entities
entities:
  - sensor.setlistfm_yourname_concerts
  - sensor.yourname_total_concerts
  - sensor.yourname_unique_concert_visits
  - sensor.yourname_next_concert
  - sensor.setlistfm_yourname_last_update
  - button.yourname_refresh
```

**Quick Upcoming Concerts**:
```yaml
type: markdown
title: 🎤 Upcoming Shows
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') or '' %}
  {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
  {% for concert in upcoming %}
  🔜 {{ concert.replace('(Upcoming)', '') }}
  {% endfor %}
```

For more dashboard examples see [DASHBOARDS.md](DASHBOARDS.md).

### Automation Example

Send a notification when you have an upcoming concert:

```yaml
automation:
  - alias: "Upcoming Concert Reminder"
    trigger:
      - platform: state
        entity_id: sensor.setlistfm_yourname_concerts
    condition:
      - condition: template
        value_template: >
          {{ 'Upcoming' in (state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') or '') }}
    action:
      - service: notify.mobile_app
        data:
          title: "Concert Reminder"
          message: >
            You have upcoming concerts!
            {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

## Migration from v1.x

If you were using the old YAML-based version:

1. **Backup your configuration** - Copy your YAML config before removing it
2. **Install the new version** - Follow installation steps above
3. **Remove YAML configuration** - Delete the `setlistfm:` section from `configuration.yaml`
4. **Add via UI** - Configure through the UI as described above
5. **Update automations** - Use the actual registered sensor IDs. Old YAML `text`
   entities are not automatically migrated. The old response sensor is replaced by
   diagnostic attributes. UI-configured Concerts entities keep their existing IDs.

## Reauthentication and Removal

When an API key is rejected, Home Assistant offers **Reconfigure** on the existing
entry. Enter a replacement key in the masked field. A successful validation updates
and reloads that same entry without changing its username, options, title or entity
and device associations. Connection errors, rate limits and unexpected responses
remain visible so you can retry; do not delete the account to change a rejected key.

To remove an account, use its three-dot menu in **Settings → Devices & Services →
setlist.fm → Delete**. Home Assistant removes its entities and device association;
local polling and midnight listeners stop. This does not alter your setlist.fm
account or revoke the API key. Other users and the shared refresh action remain.

## Troubleshooting

### "Invalid API Key" Error
- Verify your API key is correct
- Check if your API key has been approved by Setlist.fm
- Request a new API key if needed

### "User Not Found" Error
Current versions no longer claim that an attendance response proves a username is
invalid. If an older version reports this error, upgrade. For an empty result, verify
the username from your profile URL (capitalization is handled automatically).

### No Concerts Showing
- Check your filter settings (upcoming/past/all)
- Verify you have concerts logged on Setlist.fm

### Upcoming Concerts not Showing

The integration can only show future-dated setlists that the attended API returns.
It is not a full concert schedule, and no fixed future-availability window is
documented or guaranteed. There is no separate upcoming-concert API endpoint
used by this integration; grouping does not add one.

### Rate Limiting

If setup reports **"Failed setup, will retry: setlist.fm rate limit reached; retry
after 21 seconds"**, wait for Home Assistant's automatic retry rather than
reloading or restarting repeatedly. The number is the remaining cooldown at the
last attempt, not a live countdown or a guarantee of recovery then. Home
Assistant's setup retry backoff can wait longer, and the provider can ask for
another delay. Initial setup needs every attendance page to succeed before
publishing a snapshot.

For an already-loaded account with automatic polling enabled, a rate-limit failure
makes its sensors unavailable and schedules one automatic recovery at or just
after the remaining cooldown expires, rather than waiting for the normal six-hour
poll. Longer provider delays are never shortened. A new cooldown, including one
extended by another account sharing the API key, defers recovery again. Successful
recovery restores sensor availability and the configured polling interval.
Manual Refresh during a cooldown does not restart the original delay or bypass
it; a successful manual refresh supersedes the pending recovery. Unloading,
reloading, stopping Home Assistant or disabling polling cancels that recovery.
Other failures retain Home Assistant's normal error handling.

With integration debug logging enabled, `custom_components.setlistfm.api`
distinguishes an upstream HTTP 429 or service-error backoff (including 503) from a
request deferred locally by the shared cooldown **before HTTP**. These messages
include the page number and delay, not credentials, usernames, URLs or response
contents. A locally deferred request does not mean another request hit the
provider. These diagnostics and date validation do not bypass provider limits.

- Each request has a 20-second timeout and at most 3 attempts, with backoff.
- Requests are paced at least one second apart per API key within Home Assistant.
- Valid `Retry-After` seconds or HTTP dates are respected. Delays above 30 seconds
  end the refresh rather than keeping setup or polling waiting; the client refuses
  further requests during its cooldown. Without valid guidance, a 429 starts a
  60-second cooldown without an immediate retry.
- Default refresh is 6 hours to avoid rate limits
- Consider increasing the refresh period if you hit rate limits frequently
- Pacing and cooldown deadlines are shared by every client using the same API key,
  including form resubmissions and automatic retries of failed
  initial setup. Different API keys remain independent. Other applications using
  the same key still consume its quota outside Home Assistant's control.
- State is kept in Home Assistant memory until restart, keyed by a credential
  fingerprint rather than stored API keys or client objects. Expired inactive state
  is reclaimed. If 128 credentials all have active requests or unexpired deadlines,
  new credentials fail explicitly until capacity is available; live cooldowns are
  never evicted to make room.

## API Behavior and Coverage

The integration uses [`GET /user/{userId}/attended`](https://api.setlist.fm/docs/1.0/resource__1.0_user__userId__attended.html)
for setup and polling. The deprecated [user-profile endpoint](https://api.setlist.fm/docs/1.0/resource__1.0_user__userId_.html)
always returns a result, even for nonexistent users, and is not used.

A metadata-confirmed empty response (`total: 0`, empty `setlist`) is accepted.
The published attended endpoint and Swagger definition do not specify how a valid
zero-attendance account differs from an unknown username. No authenticated live
checks were performed, and no public recorded empty/unknown response pair was
verified. A first-page HTTP 404 is therefore accepted during setup as **ambiguous
no attendance**, not proof of account existence or nonexistence. It produces an
empty list with an **unknown total** and `complete: false`. Check the username
yourself if this persists. Other service, authentication and malformed-response
errors remain errors, not empty successes.

All pages advertised by `total`, `page` and `itemsPerPage` are requested using `p`,
before local date sorting, filtering and the 1-50 display limit. The integration
does not assume API sort order. Inconsistent metadata, repeated IDs, short/repeated
pages and failures on later pages fail the refresh and retain the previous
successful snapshot; entities become unavailable until recovery. A malformed
individual concert is instead skipped with an aggregate warning and explicit
incomplete coverage, allowing valid concerts to remain useful. Event dates must
be valid calendar dates in exact `DD-MM-YYYY` form; unpadded or space-padded dates
are skipped, not silently normalized, so the backend and cards report incomplete
coverage consistently.

No attended-endpoint 1,000-result hard limit was verified in the public API
documentation. The client therefore does not impose one. A defensive limit of
1,000 **pages** fails the refresh explicitly, rather than silently truncating.
Any upstream refusal of a required page also fails the refresh. Pagination cannot
guarantee a transactionally consistent snapshot if upstream records change between
requests without detectable changes to totals or IDs.

The existing simplified `concerts` attribute remains
`id/date/artist{name,mbid}/venue{name,city,state,country}/song_count/url`.
Missing optional location fields use empty strings; missing names use `Unknown`.
Attribution URLs are retained and should be linked in dashboards.
Song counting supports both the [documented top-level `set` array](https://api.setlist.fm/docs/1.0/json_Setlist.html)
and the nested `sets.set` shape found in
[historical public production recordings](https://github.com/zschumacher/setlist-fm-client/blob/2b492a6fc940a484e3e4b6461a5057111ed44004/tests/cassettes/TestGetSetlist.test%5BAccept.json0%5D.yaml#L18-L36).
When both occur, the documented `set` field wins (including an empty array);
they are never counted twice. Test fixtures are synthetic examples of these shapes.

### Coverage metadata

| Concert sensor attribute | Meaning |
| --- | --- |
| `total_attended` | Upstream total before display filtering; `null` when unknown |
| `fetched_count` | Number of valid, unique concerts available before filtering |
| `skipped_count` | Invalid individual records omitted from the fetched pages |
| `complete` | Whether every advertised concert is available as a valid record |
| `completeness_reason` | `null`, `attendance_not_found`, or `invalid_records` |

### Grouped display attributes

The **Concerts shown** sensor also supplies these additive attributes; existing
`concerts`, `concert_list`, state, filtering and raw-list sorting remain unchanged:

| Attribute | Meaning |
| --- | --- |
| `concert_visits` | Filtered, bounded visit list for grouped cards |
| `grouping_rule` | `venue_day`: canonical date plus venue ID, not a claimed event identity |
| `grouping_complete` | Whether the full fetched snapshot has complete coverage and groupable identities/dates |
| `identified_visit_count` | Distinct identified venue-days before display filtering and limits |
| `unidentified_performance_count` | Performances without usable venue identity; cannot establish unique visits |
| `invalid_date_count` | Records with invalid dates that cannot be grouped |

Each `concert_visits` item contains:

```text
date
venue { id, name, city, state, country }
performances [ { id, artist { name, mbid }, song_count, url } ]
grouping_complete
performance_count
omitted_performance_count
```

`date` is canonical `DD-MM-YYYY`. `performance_count` includes all performances
in the visit; `omitted_performance_count` explicitly counts those excluded from
its `performances` payload by resource bounds. Artists are alphabetical, not
ordered as a concert bill.

The integration groups the full validated snapshot **before** applying
**Show concerts** and **Number of concerts**. The existing `number_of_concerts`
option (1-50) independently caps raw performances and grouped visits. For visits,
**All** selects nearest upcoming dates first, then latest past dates;
**Upcoming only** selects earliest first, and **Past only** selects latest first.
Today is upcoming in Home Assistant's configured time zone. Raw-list ordering
does not change.

Grouped payloads include at most **100 performances per visit** and **500
performances overall**, with explicit omission counts and card warnings rather
than silent lineup truncation. These resource bounds do not affect the native
Unique concert visits count. Unidentified performances remain separate entries
with `grouping_complete: false`, subject to the same display/resource bounds.
Card section limits count visits in grouped mode and performances otherwise;
cards only see these bounded lists, not the full fetched history.

For integration developers, `coordinator.data["concerts"]` contains the full
unfiltered API-style concert list with normalized optional fields and canonical
`set` arrays. The coordinator exposes the same metadata, naming the upstream
count `total` instead of `total_attended`, plus `pages_fetched`. There is no `user`
profile object. A successful transport refresh with `complete: false` must not
be described as a complete attendance history.

Runtime access is through the typed `entry.runtime_data` coordinator, not a
per-entry `hass.data` dictionary. `last_successful_update` is the shared UTC
timestamp; `async_manual_refresh()` is the error-aware, awaited operation for
manual controls. Unique IDs use the entry ID plus `_concerts`, `_total_concerts`,
`_unique_concert_visits`, `_next_concert`, `_last_update` and `_refresh`, with
device identifiers unchanged.

Create HA clients with `client.async_create_client(hass, api_key, userid)` so
validation and coordinator recreation share quota state. Standalone callers can
still construct `SetlistFmClient` directly, optionally injecting a
`RequestStateStore` via `request_states=`. The HA registry lives under
`hass.data["setlistfm_request_states"]`, separate from entry runtime data.

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.setlistfm: debug
```

Then restart and check: **Settings → System → Logs**

## Development

Run the regression tests on Linux (including WSL) with Python 3.14. The test
dependencies pin Home Assistant 2026.9.4; they are not runtime requirements for
installing this integration.

```bash
python -m pip install -r requirements-test.txt
python -m pytest
```

The CI matrix also runs the suite on Python 3.13 with
`requirements-test-min.txt` (Home Assistant 2025.1.4). Use a separate environment
for that historical check. Its test-only pycares 4.5 pin prevents a newer DNS
library's persistent cleanup thread from conflicting with the historical test
fixtures; neither runtime requirements nor the latest test pin are changed.

The [local mock API](devtools/setlistfm_mock/README.md) provides a loopback-only
aiohttp server, synthetic datasets, fault scenarios and real HTTP wire tests.
It needs no live API key and does not change the production endpoint or normal
integration installation.

The **Frontend** CI matrix additionally tests both matching HA frontend versions:
browser regressions and responsive light/dark screenshots, plus real mock HTTP
requests through configured integration entries, renamed native entities, the
card picker, visual editor and saved dashboard. See [CARDS.md](CARDS.md#development-verification)
for the reproducible local commands. No live API credentials are needed.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## Support

- **Issues**: [GitHub Issues](https://github.com/ianpleasance/home-assistant-setlistfm/issues)

## Credits

- Original version by [@ianpleasance](https://github.com/ianpleasance)

## License

This project is licensed under the Apache 2.0 License.
