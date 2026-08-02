#!/usr/bin/env python3
"""
Apple IPSW Firmware RSS Feed Generator

ipsw.me (IPSW Downloads) resmi API'sinden en guncel Apple firmware
(iOS/iPadOS/watchOS/tvOS/audioOS/visionOS/macOS) verilerini ceker ve
GitHub Pages icin bir RSS feed (rss.xml) uretir.

Onemli: ipsw.me API'sindeki 'url' alani zaten Apple'in kendi CDN'ine
(updates.cdn-apple.com) giden DOGRUDAN indirme linkidir. Ayri bir
"indirme sayfasi" yoktur -> RSS'teki <link> ve <enclosure url> tiklaninca
dosya direkt inmeye baslar.

Data source: https://api.ipsw.me/v4/
API docs:    https://ipsw.me/api/
"""

import json
import re
import sys
import time
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "https://api.ipsw.me/v4"
DEVICES_URL = f"{API_BASE}/devices"
DEVICE_URL_TMPL = f"{API_BASE}/device/{{identifier}}"

TIMEOUT = 15
# ipsw.me API'sini spam'lememek icin dusuk tutuyoruz ("use fairly" kurali).
MAX_WORKERS = 6
RETRY_COUNT = 3
RETRY_BACKOFF = 2.0  # saniye, her denemede katlanir

# Sadece bu identifier onekleriyle baslayan cihazlar cekilsin istenirse
# virgulle ayirip IPSW_DEVICE_PREFIXES ortam degiskenine yazilabilir.
# Bos birakilirsa (varsayilan) TUM cihaz tipleri cekilir.
DEVICE_PREFIXES = [
    p.strip() for p in os.environ.get("IPSW_DEVICE_PREFIXES", "").split(",") if p.strip()
]

# identifier onekine gore platform/isletim sistemi adi
PLATFORM_MAP = {
    "iPhone": "iOS",
    "iPod": "iOS",
    "iPad": "iPadOS",
    "Watch": "watchOS",
    "AppleTV": "tvOS",
    "AudioAccessory": "audioOS",
    "RealityDevice": "visionOS",
    "Mac": "macOS",
    "iBridge": "bridgeOS",
}

UA_HEADERS = {"User-Agent": "mifrm-ipsw-rss/1.0 (+https://github.com/)"}


def fetch_json(url, timeout=TIMEOUT):
    """429/5xx durumunda kisa bir bekleyip yeniden dener."""
    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers=UA_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                return None
            time.sleep(RETRY_BACKOFF * attempt)
        except Exception as e:
            last_err = e
            time.sleep(RETRY_BACKOFF * attempt)
    print(f"WARN: {url} basarisiz oldu ({last_err})", file=sys.stderr)
    return None


def fetch_devices():
    data = fetch_json(DEVICES_URL, timeout=30)
    if not data:
        print("ERROR: Cihaz listesi cekilemedi", file=sys.stderr)
        sys.exit(1)
    # API: [{"name": "iPhone 14 Pro", "identifier": "iPhone15,2"}, ...]
    devices = [d for d in data if d.get("identifier")]
    if DEVICE_PREFIXES:
        devices = [
            d for d in devices
            if any(d["identifier"].startswith(p) for p in DEVICE_PREFIXES)
        ]
    return devices


def platform_name(identifier):
    match = re.match(r"^([A-Za-z]+)", identifier or "")
    prefix = match.group(1) if match else ""
    return PLATFORM_MAP.get(prefix, "Firmware")


def human_size(num_bytes):
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def iso_to_rfc822(iso_str):
    """'2026-07-27T17:38:04Z' -> 'Mon, 27 Jul 2026 17:38:04 +0000'"""
    if not iso_str:
        return None
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except ValueError:
        return None


def latest_firmware(firmwares):
    """
    En guncel firmware'i secer. Once yayin tarihine (releasedate),
    o yoksa yukleme tarihine (uploaddate) gore siralar.
    """
    if not firmwares:
        return None

    def sort_key(fw):
        return fw.get("releasedate") or fw.get("uploaddate") or ""

    return max(firmwares, key=sort_key)


def fetch_device_latest(device):
    identifier = device["identifier"]
    url = DEVICE_URL_TMPL.format(identifier=identifier)
    data = fetch_json(url)
    if not data:
        return None
    firmwares = data.get("firmwares") or []
    fw = latest_firmware(firmwares)
    if not fw or not fw.get("url"):
        return None
    return {
        "name": data.get("name") or device.get("name") or identifier,
        "identifier": identifier,
        "platform": platform_name(identifier),
        "version": fw.get("version", "Unknown"),
        "buildid": fw.get("buildid", "Unknown"),
        "filesize": fw.get("filesize"),
        "filesize_human": human_size(fw.get("filesize")),
        "sha1sum": fw.get("sha1sum", "Unknown"),
        "md5sum": fw.get("md5sum", "Unknown"),
        "signed": bool(fw.get("signed")),
        "releasedate": fw.get("releasedate"),
        "uploaddate": fw.get("uploaddate"),
        "download_url": fw["url"],
    }


def fetch_all_latest():
    devices = fetch_devices()
    print(f"Fetched {len(devices)} devices")

    results = []
    total = len(devices)
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_device_latest, d): d for d in devices}
        for future in as_completed(futures):
            done += 1
            if done % 25 == 0:
                print(f"  Progress: {done}/{total}")
            try:
                item = future.result()
                if item:
                    results.append(item)
            except Exception as e:
                print(f"WARN: {futures[future].get('identifier')}: {e}", file=sys.stderr)

    print(f"Found {len(results)} firmware entries")
    return results


def generate_rss(items):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    rss_items = []
    for item in sorted(items, key=lambda r: r["identifier"]):
        # Baslik: "iPhone 14 Pro - iOS 17.5.1 (21F90)"
        title = f"{item['name']} - {item['platform']} {item['version']} ({item['buildid']})"
        signed_txt = "Yes" if item["signed"] else "No (unsigned - restore/downgrade not possible via TSS)"
        description = (
            f"Device: {item['name']} ({item['identifier']})\n"
            f"Platform: {item['platform']}\n"
            f"Version: {item['version']}\n"
            f"Build: {item['buildid']}\n"
            f"Size: {item['filesize_human']}\n"
            f"SHA1: {item['sha1sum']}\n"
            f"Signed by Apple: {signed_txt}\n"
            f"Download: {item['download_url']}"
        )
        guid = f"{item['identifier']}_{item['buildid']}"
        pub_date = iso_to_rfc822(item.get("releasedate")) or iso_to_rfc822(item.get("uploaddate")) or now

        length_attr = f' length="{item["filesize"]}"' if item.get("filesize") else ""

        rss_items.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <link>{escape(item['download_url'])}</link>
      <enclosure url="{escape(item['download_url'])}"{length_attr} type="application/octet-stream"/>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <pubDate>{pub_date}</pubDate>
      <category>{escape(item['platform'])}</category>
    </item>""")

    owner = os.environ.get('GITHUB_REPOSITORY_OWNER', 'username')
    repo = os.environ.get('GITHUB_REPOSITORY', 'ipsw-rss').split('/')[-1]
    site = f"https://{owner}.github.io/{repo}/"

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Apple IPSW Firmware Feed</title>
    <link>{site}</link>
    <description>Latest official Apple IPSW firmware downloads (iOS, iPadOS, watchOS, tvOS, audioOS, visionOS, macOS) via ipsw.me API</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{site}rss.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(rss_items)}
  </channel>
</rss>"""
    return rss


def generate_json(items):
    return json.dumps(items, indent=2, ensure_ascii=False)


def main():
    print("=== Apple IPSW RSS Generator ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")

    items = fetch_all_latest()

    if not items:
        print("WARNING: No firmware found! Generating empty feed.")

    rss_content = generate_rss(items)
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("Wrote rss.xml")

    json_content = generate_json(items)
    with open("ipsw.json", "w", encoding="utf-8") as f:
        f.write(json_content)
    print("Wrote ipsw.json")

    print(f"Done! {len(items)} firmware entries.")


if __name__ == "__main__":
    main()
