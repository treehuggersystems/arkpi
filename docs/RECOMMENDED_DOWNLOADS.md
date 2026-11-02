# Recommended Downloads

Things worth adding to ARK while the internet still works. Everything here is
free and either public domain or freely licensed.

## PDF manuals → `/opt/offline-data/manuals/`

Drop PDFs in the folder and they show up in the Library automatically. Add a
friendly title in `MANUAL_TITLES` in `app/main.py` if you like.

| Manual | Why | Where to find it |
|---|---|---|
| **Where There Is No Doctor** (Hesperian) | The classic village-medicine book | hesperian.org (free PDF) |
| **Where There Is No Dentist** (Hesperian) | Dental care without a dentist | hesperian.org |
| **A Book for Midwives** (Hesperian) | Childbirth without a hospital | hesperian.org |
| **USDA Complete Guide to Home Canning** (2015) | The canning reference | nchfp.uga.edu |
| **FM 21-76 US Army Survival Manual** (1992) | Classic survival manual | Public domain; many mirrors |
| **FM 3-25.26 Map Reading & Land Navigation** | Map & compass, MGRS | armypubs.army.mil |
| **FM 21-10 Field Hygiene and Sanitation** | Field sanitation | armypubs.army.mil |
| **ATP 4-25.13 Casualty Evacuation** | Moving casualties | armypubs.army.mil |
| **TC 4-02.1 First Aid** | Current Army first aid | armypubs.army.mil |
| **ARRL Ham Radio License Manual** (paid) or **HamStudy** question pools | Get licensed | arrl.org / ncvec.org (question pools are public domain) |
| **Ball Blue Book** (paid) | Canning recipes | Retail |
| Owner's manuals for your **generator, vehicles, radios, chainsaw, well pump, furnace** | You'll need them | Manufacturer sites |

> `fm5-34.pdf` in the manuals folder is actually a saved 404 web page, not a
> PDF. ARK hides it. `FM_5_34.pdf` is the real one, so the bad file can be deleted.

## Kiwix libraries (ZIM) → `/opt/kiwix/`

`scripts/fetch-zims.sh` downloads the curated set (~21 GB). Extras to consider:

| ZIM | Size | Notes |
|---|---|---|
| `wikipedia_en_all_maxi` | ~110 GB | All of English Wikipedia with images. `nopic` ≈ 55 GB, `mini` ≈ 12 GB |
| `wikihow_en_all_maxi` | ~50+ GB | How-to everything (check the catalog for current builds) |
| `gutenberg_en_lcc-t` | 13 GB | Project Gutenberg: Technology |
| `wiktionary_en_all_nopic` | ~5 GB | Dictionary |
| `khanacademy` / `phet` | varies | Education for kids |
| `survivorlibrary.com_en_all` | 220 GB | Huge archive of pre-industrial skills books |
| `electronics.stackexchange.com` | 4.2 GB | Electronics repair Q&A |
| `canadian-prepper_*`, `urban-prepper_*` | 1–3 GB each | Prepper video channels |

Browse everything at https://library.kiwix.org. After adding files, run the
`kiwix-manage` loop at the bottom of `scripts/fetch-zims.sh` (or re-run the
script) to rebuild `library.xml`; kiwix-serve picks it up automatically.

## Maps → `/opt/offline-data/maps/`

`scripts/fetch-maps.sh` downloads World (z0–7), US (z0–10) and a regional
street-level extract. Change `REGION_BBOX` for more/other states. Each extra
state at street level is roughly 300–800 MB.

## Software installers (for rebuilding offline)

- Raspberry Pi OS image + **Raspberry Pi Imager**
- This repo + `pip download -r requirements.txt -d wheels/` (offline Python packages)
- `kiwix-tools` .deb packages and the `pmtiles` binary for ARM64
- Kiwix apps for Android/iOS/desktop (read ZIMs directly on a phone)
- **Organic Maps** / **OsmAnd** with offline map packs on phones
- CHIRP (radio programming) + drivers for your programming cable
