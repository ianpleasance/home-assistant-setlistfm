# 📚 Setlist.fm Integration v2.0 - Documentation Index

Welcome to the completely rewritten Setlist.fm integration for Home Assistant!

## 🚀 Quick Start

**New user?** → Start here: **[INSTALL.md](INSTALL.md)**

**Upgrading from v1.x?** → Read this first: **[MIGRATION.md](MIGRATION.md)**

**Want to see what's new?** → Check out: **[CHANGELOG.md](CHANGELOG.md)**

---

## 📖 Documentation Files

### Getting Started
- **[INSTALL.md](INSTALL.md)** - Quick installation guide
  - Prerequisites
  - Installation methods (Manual & HACS)
  - First-time setup
  - Troubleshooting

### User Documentation
- **[README.md](README.md)** - Complete feature documentation
  - All features explained
  - Configuration options
  - Usage examples
  - Lovelace cards
  - Automations
  - Services
  - FAQ

- **[DASHBOARDS.md](DASHBOARDS.md)** - Beautiful dashboard examples
  - Complete layouts with emojis
  - Individual card templates
  - Stats and countdown cards
  - Calendar views
  - Mushroom card examples
  - Custom styling options

### Migration & Changes
- **[MIGRATION.md](MIGRATION.md)** - v1.x to v2.x migration guide
  - Step-by-step migration
  - Breaking changes
  - Entity mapping
  - Before/after examples
  - Rollback instructions

- **[COMPARISON.md](COMPARISON.md)** - Visual before/after comparison
  - Side-by-side comparisons
  - Architecture changes
  - User experience improvements
  - Benefits summary

- **[CHANGELOG.md](CHANGELOG.md)** - Detailed change history
  - What's new in v2.0
  - Bug fixes
  - Technical improvements
  - Performance metrics

### Overview
- **[SUMMARY.md](SUMMARY.md)** - Executive summary
  - Key improvements
  - File structure
  - Quick reference
  - Testing checklist

---

## 🗂️ File Structure

### Integration Files (The actual code)
```
setlistfm/
├── __init__.py           # Main setup & coordinator
├── config_flow.py        # UI configuration
├── const.py              # Constants
├── sensor.py             # Sensor entities
├── manifest.json         # Integration metadata
├── strings.json          # UI labels
├── hacs.json            # HACS configuration
└── translations/
    └── en.json          # Translations
```

### Documentation Files (What you're reading)
```
setlistfm/
├── README.md            # Main documentation
├── INSTALL.md           # Installation guide
├── DASHBOARDS.md        # Dashboard examples with emojis
├── MIGRATION.md         # Migration guide
├── COMPARISON.md        # Before/after comparison
├── CHANGELOG.md         # Change history
├── SUMMARY.md           # Quick overview
└── INDEX.md             # This file
```

---

## 🎯 What Do I Need to Read?

### I'm a new user and want to install this
→ **[INSTALL.md](INSTALL.md)** (5 min read)

### I want to know all the features
→ **[README.md](README.md)** (15 min read)

### I want beautiful dashboard examples
→ **[DASHBOARDS.md](DASHBOARDS.md)** (10 min read)

### I'm upgrading from the old version
→ **[MIGRATION.md](MIGRATION.md)** (10 min read)

### I want to see what changed
→ **[COMPARISON.md](COMPARISON.md)** (8 min read)

### I want detailed technical changes
→ **[CHANGELOG.md](CHANGELOG.md)** (12 min read)

### I just want a quick overview
→ **[SUMMARY.md](SUMMARY.md)** (5 min read)

---

## ⚡ Quick Reference

### Installation
```bash
# 1. Copy files
cp -r setlistfm /config/custom_components/

# 2. Restart Home Assistant

# 3. Add integration via UI
Settings → Devices & Services → Add Integration → Setlist.fm
```

### Entities Created
- `sensor.setlistfm_{name}_concerts` - Concert list
- `sensor.setlistfm_{name}_last_update` - Last update timestamp

### Configuration Options
- **Refresh Period**: 1-24 hours (default: 6)
- **Number of Concerts**: 1-50 (default: 10)
- **Date Format**: DD-MM-YYYY, MM-DD-YYYY, etc.
- **Show Concerts**: All, Upcoming only, Past only

### Common Card Example
```yaml
type: markdown
title: My Concerts
content: |
  {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

---

## 🔗 External Resources

- **Setlist.fm API**: https://api.setlist.fm/docs/
- **Get API Key**: https://www.setlist.fm/settings/api
- **GitHub Repository**: https://github.com/ianpleasance/home-assistant-setlistfm
- **Home Assistant**: https://www.home-assistant.io
- **HACS**: https://hacs.xyz

---

## ❓ Common Questions

### How do I get my User ID?
Go to your Setlist.fm profile. The URL will be `https://www.setlist.fm/user/YOUR_USER_ID`

### How do I get an API key?
Visit https://www.setlist.fm/settings/api and request one (instant approval for personal use)

### Can I add multiple users?
Yes! Just add the integration multiple times with different credentials.

### Will this work with the old YAML config?
No, you need to migrate to the UI-based configuration. See [MIGRATION.md](MIGRATION.md)

### What if I want to change settings?
Click "Configure" on the integration in Devices & Services.

### How do I force a refresh?
Use the `setlistfm.force_refresh_{entry_id}` service in Developer Tools.

---

## 🐛 Troubleshooting

### Integration not showing up
1. Verify files are in `/config/custom_components/setlistfm/`
2. Restart Home Assistant
3. Check logs: Settings → System → Logs

### "Invalid API Key" error
1. Verify API key from https://www.setlist.fm/settings/api
2. Check for extra spaces when copy/pasting
3. Ensure key is approved

### No concerts showing
1. Verify you have concerts logged on Setlist.fm
2. Check filter settings (All/Upcoming/Past)
3. Look at `total_attended` attribute

### Need more help?
Enable debug logging:
```yaml
logger:
  logs:
    custom_components.setlistfm: debug
```

Then check: Settings → System → Logs

---

## 📊 Version Comparison

| Feature | v1.x | v2.x |
|---------|:----:|:----:|
| UI Configuration | ❌ | ✅ |
| YAML Configuration | ✅ | ❌ |
| Async/Non-blocking | ❌ | ✅ |
| Options Flow | ❌ | ✅ |
| Unique Entity IDs | ❌ | ✅ |
| Auto Retry | ⚠️ | ✅ |
| Error Recovery | ⚠️ | ✅ |
| Multiple Users | ⚠️ | ✅ |

---

## 🎉 Key Improvements

1. **No more YAML editing** - Everything configurable through UI
2. **No more UI freezing** - Fully async operations
3. **Better error handling** - Clear messages and auto-retry
4. **Easier multi-user** - Independent settings per user
5. **Proper HA integration** - Entity registry, device classes, etc.

---

## 📝 Contributing

Found a bug? Have a suggestion? Want to contribute?

1. Check existing issues
2. Open a new issue with details
3. PRs welcome!

---

## 📄 License

MIT License - Free to use and modify

---

## 🙏 Credits

- **Original integration**: [@ianpleasance](https://github.com/ianpleasance)
- **Setlist.fm API**: For providing the data
- **Home Assistant**: For the amazing platform
- **Community**: For feedback and testing

---

**Ready to get started?** → [INSTALL.md](INSTALL.md)

**Need help?** → [README.md#troubleshooting](README.md#troubleshooting)

**Questions?** → [Open an issue](https://github.com/ianpleasance/home-assistant-setlistfm/issues)
