# Apple IPSW Firmware RSS Feed

`mifrm` (Xiaomi MIUI/HyperOS ROM feed) projesinin [ipsw.me](https://ipsw.me) resmi API'sine uyarlanmis hali. Apple'in tum cihazlari (iPhone, iPad, iPod touch, Apple Watch, Apple TV, HomePod, Vision Pro, Mac) icin **en guncel imzali firmware**'i tarar ve bir RSS feed'i (`rss.xml`) + JSON dump (`ipsw.json`) uretir.

## Onemli: Direkt indirme

`ipsw.me` API'sindeki `url` alani zaten Apple'in kendi CDN'ine
(`updates.cdn-apple.com`) giden **dogrudan** dosya linkidir. Aradaki bir
"indirme sayfasina" ugramaz. RSS'teki her `<item>` icinde:

- `<link>` -> dogrudan `.ipsw` dosyasina gider
- `<enclosure url="..." length="..." type="application/octet-stream"/>` -> RSS okuyucusu/podcast istemcisi bu urlyi otomatik indirme olarak algilar

Yani feed'deki bir ogeye tikladiginizda (veya RSS okuyucunuz enclosure'i indirdiginde) dosya **direkt inmeye baslar**, ekstra tiklama gerekmez.

## Nasil calisir

1. `GET https://api.ipsw.me/v4/devices` -> tum cihaz kimliklerini (`identifier`) ceker
2. Her cihaz icin `GET https://api.ipsw.me/v4/device/{identifier}` -> o cihazin tum firmware gecmisini ceker
3. Her cihaz icin **en yeni** (`releasedate`'e gore) firmware secilir, imzali olup olmadigi (`signed`) RSS aciklamasinda belirtilir
4. `rss.xml` ve `ipsw.json` uretilir

## Kullanim

```bash
pip install --break-system-packages -r requirements.txt  # sadece stdlib kullanir, gerek yok aslinda
python3 fetch_ipsw.py
```

Cikti: `rss.xml`, `ipsw.json`

### Sadece belirli cihaz tiplerini cekmek

Varsayilan olarak TUM cihazlar (277+ cihaz) cekilir, bu da API'ye
epey istek gonderir (kibarca, `MAX_WORKERS=6` ile). Sadece belirli
tipleri cekmek icin ortam degiskeni kullanin:

```bash
# Sadece iPhone ve iPad
IPSW_DEVICE_PREFIXES="iPhone,iPad" python3 fetch_ipsw.py
```

Kullanilabilir onekler: `iPhone`, `iPad`, `iPod`, `Watch`, `AppleTV`,
`AudioAccessory` (HomePod), `RealityDevice` (Vision Pro), `Mac`.

## GitHub Actions

`.github/workflows/update-feed.yml` her 12 saatte bir (ve manuel
tetiklemeyle) scripti calistirir, `rss.xml` + `ipsw.json` dosyalarini
commit'ler ve GitHub Pages'e deploy eder.

## RSS ogesi ornegi

```
Title: iPhone 14 Plus - iOS 26.6 (23G71)
Link/Enclosure: https://updates.cdn-apple.com/.../iPhone14,8_26.6_23G71_Restore.ipsw
Description:
  Device: iPhone 14 Plus (iPhone14,8)
  Platform: iOS
  Version: 26.6
  Build: 23G71
  Size: 9.70 GB
  SHA1: ...
  Signed by Apple: Yes
  Download: https://updates.cdn-apple.com/...
```

## Kaynak

- API: https://api.ipsw.me/v4/ (docs: https://ipsw.me/api/)
- Tum dosyalar Apple'in kendi sunucularindan (`updates.cdn-apple.com`) sunulur; bu repo hicbir firmware dosyasi barindirmaz.
