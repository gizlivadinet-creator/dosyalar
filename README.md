# Xiaomi ROM RSS Feed

Auto-updating RSS feed of official Xiaomi MIUI / HyperOS Fastboot ROM downloads, hosted on GitHub Pages.

## How it works

1. **`fetch_roms.py`** queries Xiaomi's official update server (`update.intl.miui.com`) for the latest ROM of every known device codename (~300 devices, all regions).
2. Results are written to **`rss.xml`** (RSS feed) and **`roms.json`** (JSON API).
3. **GitHub Actions** runs the script every 12 hours automatically and commits the updated files.
4. **GitHub Pages** serves the feed at `https://YOUR_USERNAME.github.io/REPO_NAME/rss.xml`.

## Setup

1. Create a new GitHub repository and push these files to it.
2. Go to **Settings → Pages → Source: GitHub Actions**.
3. The workflow runs on push and every 12 hours via cron.

## Feed URL

```
https://YOUR_USERNAME.github.io/REPO_NAME/rss.xml
```

## Data sources

- ROM data: `https://update.intl.miui.com/updates/miota-fullrom.php` (Xiaomi's official server, no auth needed)
- Codename list: [AllXiaomiDeviceCodes](https://github.com/chebishev/AllXiaomiDeviceCodes)

## Files

| File | Description |
|------|-------------|
| `fetch_roms.py` | Fetches ROMs and generates feeds |
| `.github/workflows/update-feed.yml` | GitHub Actions cron + deploy |
| `index.html` | Landing page with feed URL and stats |
| `rss.xml` | Generated RSS feed (auto-updated) |
| `roms.json` | Generated JSON data (auto-updated) |
