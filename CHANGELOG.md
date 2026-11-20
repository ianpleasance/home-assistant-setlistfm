# Changelog

All notable changes to the setlist.fm Home Assistant integration are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- Wait for Home Assistant's active frontend registry before registering cards,
  retain pending editor account changes across focus, and surface upstream
  incomplete attendance even when returned concert records are valid.
- Keep successful-refresh timestamps stable across attribute reads and failed
  refreshes; validate refresh action targets and preserve existing entity IDs.
- Use the supported attended endpoint for setup and polling instead of deprecated
  profile validation; preserve empty accounts without claiming username existence.
- Fetch and validate all advertised attendance pages before filtering. Failed
  later pages retain the previous snapshot instead of publishing partial history.
- Count songs in both documented `set` and recorded `sets.set` representations,
  preserve attribution URLs, and isolate malformed concerts and optional fields.
- Share finite timeouts, bounded retries, request pacing, and `Retry-After`
  cooldowns between setup and polling without hiding cancellation or API errors.
- Preserve API-key cooldowns across fresh validation clients and failed-setup
  coordinator retries using bounded Home Assistant-owned request state.
- Recover loaded accounts automatically after a rate-limit cooldown on both
  supported Home Assistant versions, then restore normal polling. Retain shared
  deadlines and refresh-action errors, and cancel pending recovery on unload,
  reload, shutdown or disabled polling.

### Added
- Native Unique concert visits sensor using full-snapshot venue-day grouping,
  with unknown totals for incomplete or unidentified attendance and no extra API calls.
- Additive `concert_visits` attributes and opt-in **Group by concert visit**
  across all four bundled card presets; alphabetical lineups retain individual
  setlist links and song counts, with explicit identity and resource-limit warnings.
- Explicit upstream total, fetched/skipped counts and completeness attributes.
- Bundled Complete, Compact, Deluxe and Mobile cards with automatic loading,
  visual account editors, previews and responsive Home Assistant theme support.
- Native Total concerts, Next concert, Last successful update and Refresh
  entities; reauthentication for replacing rejected API keys in place.
- Local mock HTTP API, real-clock request-pacing coverage, and dual-version
  Python/browser CI including mock-API-to-saved-card smoke tests.
- An upstream HACS repository button with explicit installation confirmation.

### Changed
- The existing 1-50 Number of concerts option independently limits raw
  performances and grouped visits; existing sensor meanings, IDs and default
  ungrouped card behavior are preserved.
- Minimum supported Home Assistant version is 2025.1.0; the test environments
  exercise HA 2025.1.4 and 2026.9.4 with their matching frontend packages.
- New entry titles use the optional friendly name or normalized username rather
  than a deprecated profile display name. Existing entry and registry IDs are unchanged.

## [2.0.20] - 2026-03-05

### Fixed
- **`concerts_data` unbound variable** — if all three retry attempts raised a connection
  error the variable was never assigned, causing an `UnboundLocalError` on return.
  Initialised to `{}` before the loop as a safe default.
- **Raw `aiohttp.ClientSession`** — coordinator was creating its own session instead of
  using `async_get_clientsession(hass)`. Sessions not managed by HA are never properly
  closed on integration unload. Switched to the HA-managed session throughout.
- **`LastUpdateSensor` device_class** — sensor had `device_class` removed to work around
  a type mismatch: `native_value` was returning an ISO string while HA expected a `datetime`
  object. Root cause fixed: `native_value` now returns the `datetime` object directly and
  `_attr_device_class = SensorDeviceClass.TIMESTAMP` is set correctly.
- **`manifest.json` duplicate `requirements` key** — file contained `"requirements": []`
  and `"requirements": ["aiohttp>=3.8.0"]`. Duplicate JSON keys are invalid; the first
  (empty) entry is removed.
- **`force_refresh_{entry_id}` service** — service name embedded a raw UUID making it
  undiscoverable in the UI and unscriptable in automations without knowing the internal
  entry ID. Replaced with a single static `setlistfm.refresh` service that accepts an
  optional `entry_id` field; if omitted all entries are refreshed.

### Added
- `SensorStateClass.MEASUREMENT` on `SetlistFmConcertsSensor` — count sensor now graphs
  correctly in HA history and works with statistics.
- `device_info` on both sensors — sensors now appear grouped under a device in
  **Settings → Devices & Services** rather than floating unattached.
- `from __future__ import annotations` in `__init__.py` and `sensor.py`.
- `Platform.SENSOR` enum used for `PLATFORMS` list (replaces deprecated plain string).
- `services.yaml` now documents the `refresh` service with field descriptions.
- `strings.json` and all translation files (`en`, `de`, `fr`, `it`) updated with
  `services.refresh` translation block.
- `user_not_found` error string added to `de.json`, `fr.json`, and `it.json` (was
  missing from non-English translations).

### Changed
- `translation_strings` dict parameter removed from `SetlistFmConcertsSensor.__init__`;
  `at/in/on/Upcoming` are now module-level constants in `sensor.py`.
- Documentation files moved from `custom_components/setlistfm/` to repository root
  (`CHANGELOG.md`, `INSTALL.md`, `DASHBOARDS.md`). Only Python source files and
  `translations/` should live inside `custom_components/`.
- `manifest.json` documentation URL corrected (was pointing to a differently-named
  repository).
- Version bumped to `2.0.20`.

### Removed
- `push.sh` — personal deployment helper script; should not be distributed.
- `custom_components/setlistfm/INDEX.md` — navigation stub with no end-user value.
- `custom_components/setlistfm/DASHBOARD_INDEX.md` — navigation stub with no end-user value.
- `component.setlistfm` block removed from `en.json` (strings are now constants in
  `sensor.py`; the block was unused by the translation pipeline).

---

## [2.0.0] - 2025 (Complete Rewrite)

### Major Features

#### UI Configuration
- **Config Flow**: Complete UI-based setup - no YAML required!
- **Options Flow**: Change settings without removing and re-adding the integration
- **Multiple Users**: Easy to add and manage multiple Setlist.fm accounts
- **Validation**: Real-time validation of API keys and user IDs during setup

#### Performance Improvements
- **Async/Await**: Non-blocking API calls using `aiohttp`
- **Coordinator Pattern**: Efficient data updates using Home Assistant's DataUpdateCoordinator
- **Rate Limit Handling**: Intelligent retry logic with exponential backoff
- **No UI Freezing**: All operations are asynchronous

#### Better Entities
- **Unique IDs**: Proper entity registry integration
- **Attributes**: Rich attribute data including full concert JSON

### Bug Fixes

- Fixed multiple timer registrations (v1.x registered one timer per user, all updating all users)
- Fixed blocking API calls that froze the UI
- Fixed no cleanup on integration removal
- Fixed no unique IDs for entities
- Fixed rate limiting causing permanent failures

### Breaking Changes from v1.x

1. Entity domain change: `text.` → `sensor.`
2. Service names changed (see Services section in README)
3. No YAML configuration — must configure through UI
4. Entity IDs regenerated with proper unique IDs

---

## [1.0.0] - Original

- Initial release with YAML configuration
- Basic concert list display
- Synchronous API calls
- Manual entity state management
