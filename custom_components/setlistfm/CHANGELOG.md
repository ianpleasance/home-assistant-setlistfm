# Changelog

## Version 2.0.0 (Complete Rewrite)

### 🎉 Major Features

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
- **Device Class**: Last update sensor uses timestamp device class
- **Attributes**: Rich attribute data including full concert JSON
- **State Classes**: Proper sensor configuration

### 🔧 Technical Improvements

#### Code Quality
1. **Modern Architecture**:
   - Follows Home Assistant 2024+ best practices
   - Uses async/await throughout
   - Proper error handling with custom exceptions
   - Type hints for better IDE support

2. **Better Error Handling**:
   - `ConfigEntryAuthFailed` for invalid API keys
   - `UpdateFailed` for temporary failures
   - Detailed error messages in sensor attributes
   - Automatic retry on connection failures

3. **Proper Cleanup**:
   - `async_unload_entry` for proper cleanup
   - Services unregistered on removal
   - No memory leaks

4. **Translation System**:
   - Uses Home Assistant's built-in translation system
   - Separate strings.json for UI labels
   - Multi-language support ready

#### API Improvements
- **Retry Logic**: 3 attempts with 5-second delays for rate limiting
- **Connection Pooling**: Efficient use of aiohttp sessions
- **Error Recovery**: Graceful handling of API failures
- **Status Codes**: Proper HTTP status code handling

### 📊 Entity Changes

#### New Sensor Structure
**Concerts Sensor** (`sensor.setlistfm_{name}_concerts`):
- **State**: Number of concerts (was stored in text entity)
- **Attributes**:
  - `concerts`: Full JSON array of concert data (new!)
  - `concert_list`: Formatted text list (same as before)
  - `total_attended`: Total count regardless of filters (new!)

**Last Update Sensor** (`sensor.setlistfm_{name}_last_update`):
- **State**: Timestamp with proper device class
- **Attributes**:
  - `last_update_success`: Boolean success flag (new!)
  - `last_error`: Error message if failed (new!)

**Removed**:
- `sensor.setlistfm_{name}_response` - Now part of last_update attributes

### ⚙️ Configuration Changes

#### Before (v1.x - YAML)
```yaml
setlistfm:
  users:
    - userid: "user123"
      name: "MyName"
      api_key: "key123"
      refresh_period: 6
      number_of_concerts: 10
      date_format: "%d-%m-%Y"
      show_concerts: "all"
```

#### After (v2.x - UI)
1. Add integration through UI
2. Enter user ID and API key
3. Configure options in Options Flow

### 🔄 Migration Required

#### Breaking Changes
1. **Entity Domain Change**: `text.` → `sensor.`
2. **Service Names**: Now include entry_id
3. **No YAML Config**: Must configure through UI
4. **Entity IDs**: Regenerated with proper unique IDs

#### What You Need to Update
- [ ] Remove YAML configuration
- [ ] Update entity IDs in automations
- [ ] Update entity IDs in Lovelace cards
- [ ] Update service calls to include entry_id
- [ ] Update any templates referencing old entities

See [MIGRATION.md](MIGRATION.md) for detailed instructions.

### 🐛 Bug Fixes

1. **Fixed**: Multiple timer registrations (v1.x registered one timer per user, all updating all users)
2. **Fixed**: Blocking API calls that froze the UI
3. **Fixed**: No cleanup on integration removal
4. **Fixed**: Translation files loaded from disk on every update
5. **Fixed**: No unique IDs for entities
6. **Fixed**: Duplicate date comparison in concert filtering
7. **Fixed**: No proper error states for entities
8. **Fixed**: Rate limiting caused permanent failures

### 📝 Documentation

- ✅ Comprehensive README with examples
- ✅ Detailed migration guide
- ✅ Troubleshooting section
- ✅ Usage examples for Lovelace
- ✅ Automation examples

### 🔒 Security

- API keys now stored securely in config entries
- No sensitive data in state attributes
- Proper error messages without exposing credentials

### ♿ Accessibility

- Proper device classes for better voice assistant integration
- Clear entity naming
- Descriptive attributes

---

## Version 1.0.0 (Original)

- Initial release with YAML configuration
- Basic concert list display
- Synchronous API calls
- Manual entity state management

---

## Detailed Improvements Comparison

| Feature | v1.x | v2.x | Impact |
|---------|------|------|--------|
| Configuration | YAML only | UI Config Flow | ⭐⭐⭐⭐⭐ |
| API Calls | Sync (blocking) | Async (non-blocking) | ⭐⭐⭐⭐⭐ |
| Error Handling | Basic logging | Rich exceptions + recovery | ⭐⭐⭐⭐ |
| Entity Registry | No unique IDs | Proper unique IDs | ⭐⭐⭐⭐⭐ |
| Options Changes | Remove/re-add | Options flow | ⭐⭐⭐⭐ |
| Rate Limiting | Basic retry | Intelligent backoff | ⭐⭐⭐⭐ |
| Multiple Users | Multiple timers | Single coordinator each | ⭐⭐⭐⭐ |
| Cleanup | None | Proper unload | ⭐⭐⭐ |
| Documentation | Basic | Comprehensive | ⭐⭐⭐⭐ |
| Type Safety | None | Type hints | ⭐⭐⭐ |
| Translations | Manual loading | HA system | ⭐⭐⭐ |
| Device Class | None | Proper classes | ⭐⭐⭐ |

## Code Statistics

### Lines of Code
- **v1.x**: ~200 lines in single file
- **v2.x**: ~800 lines across proper modules

### File Structure
**v1.x**:
```
setlistfm/
├── __init__.py
├── manifest.json
└── translations/
    └── en.json
```

**v2.x**:
```
setlistfm/
├── __init__.py           (coordinator + setup)
├── config_flow.py        (UI configuration)
├── const.py              (constants)
├── sensor.py             (sensor entities)
├── manifest.json         (updated)
├── strings.json          (UI labels)
├── translations/
│   └── en.json
├── README.md             (comprehensive docs)
├── MIGRATION.md          (migration guide)
└── hacs.json            (HACS config)
```

## Performance Metrics

### API Call Time Impact
- **v1.x**: Blocks event loop for 2-5 seconds per user
- **v2.x**: Async, no blocking (0ms impact on event loop)

### Memory Usage
- **v1.x**: Translations loaded on every update
- **v2.x**: Loaded once at setup

### Update Efficiency
- **v1.x**: N users → N timer callbacks → N×N updates
- **v2.x**: N users → N coordinators → N updates

## Future Enhancements

Possible future additions:
- [ ] Artist/venue search sensors
- [ ] Upcoming concert notifications
- [ ] Calendar integration
- [ ] Setlist display
- [ ] Venue maps integration
- [ ] Concert statistics sensor
- [ ] Multi-language translations

## Acknowledgments

- Original integration: [@ianpleasance](https://github.com/ianpleasance)
- Home Assistant community for feedback and testing
- Setlist.fm for providing the API
