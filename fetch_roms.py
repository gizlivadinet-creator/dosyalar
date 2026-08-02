#!/usr/bin/env python3
"""
Xiaomi MIUI/HyperOS ROM RSS Feed Generator

Fetches latest ROM data from Xiaomi's official update servers
and generates an RSS feed (rss.xml) for GitHub Pages.

Data source: https://update.intl.miui.com/updates/miota-fullrom.php
Codename list: https://github.com/chebishev/AllXiaomiDeviceCodes
"""

import json
import re
import urllib.request
import urllib.parse
import sys
import os
import time
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://update.intl.miui.com/updates/miota-fullrom.php"
CODENAME_LIST_URL = "https://raw.githubusercontent.com/chebishev/AllXiaomiDeviceCodes/master/codenames_as_keys.json"
# superota.d.miui.com her istege 403 donuyor; bigota calisan mirror.
DOWNLOAD_MIRROR = "https://bigota.d.miui.com"
TIMEOUT = 12
MAX_WORKERS = 30

# Region suffixes to try for each base codename
# (suffix, region_param, region_display_name)
REGION_VARIANTS = [
    ("_global", "global", "Global"),
    ("_eea_global", "eea", "EEA"),
    ("_ru_global", "ru", "Russia"),
    ("_in_global", "in", "India"),
    ("_tr_global", "tr", "Turkey"),
    ("_id_global", "id", "Indonesia"),
    ("_tw_global", "tw", "Taiwan"),
    ("_jp_global", "jp", "Japan"),
    ("_cn", "cn", "China"),
]


def fetch_json(url, timeout=TIMEOUT):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_codenames():
    data = fetch_json(CODENAME_LIST_URL, timeout=30)
    if not data:
        print("ERROR: Could not fetch codename list", file=sys.stderr)
        sys.exit(1)
    return data


def query_rom(device, region):
    url = f"{API_URL}?d={urllib.parse.quote(device)}&b=F&r={region}&n=&l=en_US"
    data = fetch_json(url)
    if not data:
        return None
    rom = data.get("LatestFullRom")
    if not isinstance(rom, dict) or not rom.get("filename"):
        return None
    return rom


def path_version(filename, fallback):
    """
    Indirme klasoru adini DOSYA ADINDAN cikarir.
    API'nin 'version' alani bazen klasor adiyla uyusmuyor, orn:
      version  -> V816.0.4.0.TJBMIXM   (404 verir)
      filename -> umi_global_images_OS1.0.4.0.TJBMIXM_...  (dogru klasor)
    """
    match = re.search(r"_images_([^_]+)_", filename or "")
    return match.group(1) if match else fallback


def display_name(market_names, base_codename):
    """ROM adi olarak kod adi degil, pazar adini kullan (orn. 'Xiaomi 17 Ultra')."""
    if isinstance(market_names, list) and market_names:
        return market_names[0]
    if isinstance(market_names, str) and market_names.strip():
        return market_names.strip()
    return base_codename


def try_all_regions(base_codename, market_names):
    roms = []
    for suffix, region, region_name in REGION_VARIANTS:
        device = f"{base_codename}{suffix}"
        rom = query_rom(device, region)
        if rom:
            filename = rom.get("filename", "")
            version = rom.get("version", "Unknown")
            folder = path_version(filename, version)
            roms.append({
                "device": device,
                "base_codename": base_codename,
                "market_names": market_names,
                "name": display_name(market_names, base_codename),
                "region": region_name,
                "version": version,
                "filename": filename or "Unknown",
                "filesize": rom.get("filesize", "Unknown"),
                "codebase": rom.get("codebase", "Unknown"),
                "md5": rom.get("md5", "Unknown"),
                "download_url": f"{DOWNLOAD_MIRROR}/{folder}/{filename}",
            })
            break
    return roms


def fetch_all_roms():
    codenames = fetch_codenames()
    print(f"Fetched {len(codenames)} base codenames")

    all_roms = []
    total = len(codenames)
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(try_all_regions, codename, names): codename
            for codename, names in codenames.items()
        }
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"  Progress: {done}/{total}")
            try:
                roms = future.result()
                all_roms.extend(roms)
            except Exception:
                pass

    print(f"Found {len(all_roms)} ROMs")
    return all_roms


def generate_rss(roms):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    items = []
    for rom in sorted(roms, key=lambda r: r["device"]):
        # Baslik: kod adi degil pazar adi -> "Xiaomi 17 Ultra - OS3.0.303.0.WPAMIXM"
        title = f"{rom['name']} - {rom['version']}"
        name_display = ", ".join(rom["market_names"]) if rom["market_names"] else rom["base_codename"]
        description = (
            f"Device: {name_display} ({rom['device']})\n"
            f"Region: {rom['region']}\n"
            f"Version: {rom['version']}\n"
            f"Android: {rom['codebase']}\n"
            f"Size: {rom['filesize']}\n"
            f"MD5: {rom['md5']}\n"
            f"Method: Fastboot (Full ROM)\n"
            f"Download: {rom['download_url']}"
        )
        guid = f"{rom['device']}_{rom['version']}"
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <link>{escape(rom['download_url'])}</link>
      <enclosure url="{escape(rom['download_url'])}" type="application/octet-stream"/>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <pubDate>{now}</pubDate>
      <category>{escape(rom['region'])}</category>
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Xiaomi MIUI / HyperOS ROM Feed</title>
    <link>https://{os.environ.get('GITHUB_REPOSITORY_OWNER', 'username')}.github.io/{os.environ.get('GITHUB_REPOSITORY', 'xiaomi-rom-rss').split('/')[-1]}/</link>
    <description>Latest official Xiaomi MIUI and HyperOS Fastboot ROM downloads</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="https://{os.environ.get('GITHUB_REPOSITORY_OWNER', 'username')}.github.io/{os.environ.get('GITHUB_REPOSITORY', 'xiaomi-rom-rss').split('/')[-1]}/rss.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>"""
    return rss


def generate_json(roms):
    return json.dumps(roms, indent=2, ensure_ascii=False)


def main():
    print("=== Xiaomi ROM RSS Generator ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")

    roms = fetch_all_roms()

    if not roms:
        print("WARNING: No ROMs found! Generating empty feed.")

    rss_content = generate_rss(roms)
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("Wrote rss.xml")

    json_content = generate_json(roms)
    with open("roms.json", "w", encoding="utf-8") as f:
        f.write(json_content)
    print("Wrote roms.json")

    print(f"Done! {len(roms)} ROM entries.")


if __name__ == "__main__":
    main()
