# 🎨 Ready-to-Paste Dashboard Configurations

All dashboard YAMLs are ready to copy and paste into Home Assistant's **Raw Configuration Editor**.

## 📋 How to Use

1. Go to your Home Assistant
2. Click **Settings** → **Dashboards**
3. Click on a dashboard (or create new one)
4. Click **⋮** (three dots) → **Edit Dashboard**
5. Click **⋮** again → **Raw configuration editor**
6. **Delete everything** in the editor
7. **Copy** one of the YAML files below
8. **Paste** into the editor
9. Click **Save**
10. **Important**: Replace `ian_pleasance` with your configured name (lowercase)

---

## 🎯 Dashboard Options

### 1. 📱 DASHBOARD_COMPLETE.yaml (Recommended)
**Best for: Desktop/Tablet**

**Features:**
- Header with title
- Stats row (3 columns)
- Upcoming concerts section
- Recent concerts section  
- Concert details with song counts
- Status footer

**Size:** Medium
**Info Density:** High
**Mobile Friendly:** ⭐⭐⭐

**Preview:**
```
🎸 My Concert Tracker
━━━━━━━━━━━━━━━━━━━━━━━
[Stats: 10 | 150 | 2h ago]

🎤 Upcoming Concerts
🔜 Artist at Venue...

🎸 Recently Attended
✨ Artist at Venue...

🎵 Concert Details
Full details with links...
```

---

### 2. 📦 DASHBOARD_COMPACT.yaml
**Best for: Sidebar, Small Spaces**

**Features:**
- Compact header with stats inline
- Next concert highlight
- Short recent list (3 concerts)

**Size:** Small
**Info Density:** Medium
**Mobile Friendly:** ⭐⭐⭐⭐⭐

**Preview:**
```
🎵 Concerts
10 shown | 150 total

🎯 Next Concert
Artist Name
📍 Venue
📅 Date

🎸 Recent
3 concerts...
```

---

### 3. 📱 DASHBOARD_MOBILE.yaml
**Best for: Phone Screens**

**Features:**
- Large text optimized for mobile
- Stacked layout (no columns)
- Simple formatting
- Easy to tap/read

**Size:** Medium
**Info Density:** Medium
**Mobile Friendly:** ⭐⭐⭐⭐⭐

**Preview:**
```
🎸 Concerts

🎵 10
Concerts Shown

🎫 150
Total Attended

🎤 NEXT CONCERT
Large, easy-to-read...
```

---

### 4. 💎 DASHBOARD_DELUXE.yaml
**Best for: Dedicated Concert Dashboard**

**Features:**
- Hero header
- Big stats display
- Featured next concert (detailed)
- All upcoming concerts
- Last 10 concerts with full details
- Timeline by month
- Statistics summary
- System status
- Footer with links

**Size:** Large
**Info Density:** Very High
**Mobile Friendly:** ⭐⭐

**Preview:**
```
🎸 My Concert Journey

[Big Stats: 10 | 150 | 3]

🌟 Featured: Next Show
Full details...

🔜 All Upcoming
Complete list...

✨ Recently Attended
Last 10 with details...

📅 Timeline
By month...

📊 Statistics
Full stats...
```

---

## 🎨 Customization Guide

### Change Your Name
Replace `ian_pleasance` with your configured name throughout:
```yaml
# Find this:
sensor.setlistfm_ian_pleasance_concerts

# Replace with:
sensor.setlistfm_YOURNAME_concerts
```

### Change Emojis
Customize the emojis to match your style:
```yaml
# Rock style:
🎸 🤘 🥁 ⚡ 🔥

# Pop style:
🎤 ✨ 💫 ⭐ 🌟

# Electronic:
🎧 🎛️ 💿 🔊 🌈

# Classical:
🎻 🎺 🎷 🎹 🎼
```

### Change Number of Concerts Shown
```yaml
# Show last 5 instead of 10:
{% for concert in past[:5] %}

# Show last 3:
{% for concert in past[:3] %}

# Show all:
{% for concert in past %}
```

### Add Your Profile Link
```yaml
# Update the footer link:
[My Profile](https://www.setlist.fm/user/YOUR_USERNAME)
```

---

## 🔧 Troubleshooting

### Sensors Not Found
**Error:** `Entity not found: sensor.setlistfm_ian_pleasance_concerts`

**Fix:** 
1. Check your entity names in Developer Tools → States
2. Replace `ian_pleasance` with your actual entity name
3. Entity format: `sensor.setlistfm_CONFIGUREDNAME_concerts`

### No Data Showing
**Issue:** Dashboard shows "Loading..." or "0"

**Fix:**
1. Check integration is working: Settings → Devices & Services
2. Wait for first update (may take a few minutes)
3. Force refresh using the service: `setlistfm.force_refresh_XXXXX`

### Template Errors
**Error:** Red error messages in dashboard

**Fix:**
1. Go to Developer Tools → Template
2. Test your templates there first
3. Check for typos in entity names
4. Ensure integration is loaded

---

## 💡 Pro Tips

### Test Templates First
Before adding to dashboard:
1. Go to **Developer Tools** → **Template**
2. Paste template code
3. See results immediately
4. Fix any errors
5. Copy working template to dashboard

### Mix and Match
Combine cards from different dashboards:
- Use Complete's stats row
- Add Deluxe's timeline
- Include Compact's next concert

### Create Multiple Views
Add multiple dashboard views:
- Overview (Complete)
- Details (Deluxe)
- Mobile (Mobile)

### Use Subviews
Create nested views in your dashboard:
```yaml
views:
  - title: Overview
    path: overview
    cards: [...]
  
  - title: Details
    path: details
    cards: [...]
```

---

## 📊 Dashboard Comparison

| Feature | Complete | Compact | Mobile | Deluxe |
|---------|----------|---------|--------|--------|
| Stats Row | ✅ | Inline | Stacked | ✅ Big |
| Next Concert | ❌ | ✅ | ✅ Large | ✅ Hero |
| Upcoming List | ✅ | ❌ | ✅ | ✅ Full |
| Recent List | ✅ 5 | ✅ 3 | ✅ 5 | ✅ 10 |
| Song Counts | ✅ | ❌ | ❌ | ✅ |
| Timeline | ❌ | ❌ | ❌ | ✅ |
| Statistics | ❌ | ❌ | ❌ | ✅ |
| Best For | General | Sidebar | Phone | Dedicated |

---

## 🎯 Which Should I Use?

### Start with DASHBOARD_COMPLETE.yaml
It's the best all-around option that works well on desktop and mobile.

### Then Consider:
- **On phone?** → Try MOBILE
- **Want sidebar?** → Try COMPACT  
- **Want everything?** → Try DELUXE

### Or Create Your Own!
Mix and match cards from any dashboard to create your perfect layout.

---

## 📝 File List

- `DASHBOARD_COMPLETE.yaml` - Full-featured, recommended
- `DASHBOARD_COMPACT.yaml` - Minimal, sidebar-friendly
- `DASHBOARD_MOBILE.yaml` - Phone-optimized
- `DASHBOARD_DELUXE.yaml` - Everything included
- `DASHBOARD_INDEX.md` - This guide

---

## 🎉 Quick Start

1. **Download**: Get `DASHBOARD_COMPLETE.yaml`
2. **Replace**: Change `ian_pleasance` to your name
3. **Paste**: Into Raw Configuration Editor
4. **Save**: And enjoy!

Need help? Check the [README.md](README.md) for more information.
