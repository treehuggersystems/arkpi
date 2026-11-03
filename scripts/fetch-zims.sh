#!/usr/bin/env bash
# Download the curated Kiwix (ZIM) library used by Basecamp.
#
#   scripts/fetch-zims.sh [dest_dir]        (default: /opt/kiwix)
#
# Resumable: re-run any time; finished files are skipped, partial ones resume.
# File names are dated; when a newer build exists, update the list below
# (browse https://download.kiwix.org/zim/ or https://library.kiwix.org).
set -euo pipefail

DEST="${1:-/opt/kiwix}"
MIRROR="https://download.kiwix.org/zim"
mkdir -p "$DEST"

# path-under-mirror                                                       # approx size — what it is
ZIMS=(
  # --- Survival / prepping (curated) ---
  "other/zimgit-post-disaster_en_2024-05.zim"                             # 645M  post-disaster rebuilding library
  "other/zimgit-water_en_2024-08.zim"                                     #  21M  water sourcing & treatment
  "other/zimgit-food-preparation_en_2025-04.zim"                          #  98M  food prep & preservation
  "other/zimgit-medicine_en_2024-08.zim"                                  #  70M  austere medicine
  "other/zimgit-knots_en_2024-08.zim"                                     #  28M  knots
  "other/survivors_en_all_maxi_2026-09.zim"                               # 138M  survivors wiki
  "other/trueprepper.com_en_all_2026-05.zim"                              # 1.4G  TruePrepper articles
  # --- Medical ---
  "other/wikem_en_all_maxi_2026-07.zim"                                   # 375M  WikEM emergency medicine
  "other/mdwiki_en_all_maxi_2025-11.zim"                                  # 2.3G  WikiProjectMed medical encyclopedia
  "zimit/irp.fas.org_en_military-medicine_2026-05.zim"                    #  76M  military medicine manuals
  "zimit/nhs.uk_en_medicines_2026-09b.zim"                                #  15M  NHS medicines guide
  "gutenberg/gutenberg_en_lcc-r_2026-03.zim"                              # 2.0G  Project Gutenberg: Medicine
  # --- Repair, building, energy ---
  "ifixit/ifixit_en_all_2025-12.zim"                                      # 3.6G  iFixit repair guides
  "other/appropedia_en_all_maxi_2026-02.zim"                              # 582M  appropriate technology
  "other/energypedia_en_all_maxi_2026-06.zim"                             # 800M  off-grid / renewable energy
  "stack_exchange/diy.stackexchange.com_en_all_2026-08.zim"               # 2.1G  home improvement Q&A
  "stack_exchange/mechanics.stackexchange.com_en_all_2026-08.zim"         # 340M  motor vehicle repair Q&A
  "stack_exchange/bicycles.stackexchange.com_en_all_2026-08.zim"          # 491M  bicycle repair Q&A
  "stack_exchange/woodworking.stackexchange.com_en_all_2026-08.zim"       # 106M  woodworking Q&A
  "stack_exchange/ham.stackexchange.com_en_all_2026-08.zim"               #  76M  amateur radio Q&A
  "stack_exchange/sustainability.stackexchange.com_en_all_2026-08.zim"    #  28M  sustainable living Q&A
  # --- Food & growing ---
  "gutenberg/gutenberg_en_lcc-s_2026-03.zim"                              # 4.5G  Project Gutenberg: Agriculture
  "stack_exchange/gardening.stackexchange.com_en_all_2026-08.zim"         # 927M  gardening Q&A
  "stack_exchange/cooking.stackexchange.com_en_all_2026-07.zim"           # 237M  cooking Q&A
  "stack_exchange/homebrew.stackexchange.com_en_all_2026-08.zim"          #  37M  brewing / fermentation Q&A
  "other/gardenology.org_en_all_2026-09.zim"                              # 112M  plant encyclopedia
  # --- Raspberry Pi, Linux & programming ---
  "stack_exchange/raspberrypi.stackexchange.com_en_all_2026-08.zim"       # 298M  Raspberry Pi Q&A
  "stack_exchange/arduino.stackexchange.com_en_all_2026-07.zim"           # 259M  Arduino Q&A
  "stack_exchange/unix.stackexchange.com_en_all_2026-08.zim"              # 1.3G  Unix & Linux Q&A
  "devdocs/devdocs_en_python_2026-08.zim"                                 #   4M  Python documentation
  "devdocs/devdocs_en_bash_2026-10.zim"                                   #   1M  Bash manual
  "devdocs/devdocs_en_git_2026-10.zim"                                    #   2M  Git documentation
  "devdocs/devdocs_en_sqlite_2026-10.zim"                                 #   3M  SQLite documentation
  "devdocs/devdocs_en_docker_2026-10.zim"                                 #   2M  Docker documentation
  # --- Outdoors & travel ---
  "stack_exchange/outdoors.stackexchange.com_en_all_2026-08.zim"          # 141M  outdoors / bushcraft Q&A
  "wikivoyage/wikivoyage_en_all_nopic_2026-09.zim"                        # 272M  world travel guide
)

for path in "${ZIMS[@]}"; do
  file="${path##*/}"
  if [[ -f "$DEST/$file" && ! -f "$DEST/$file.part" ]]; then
    echo "✓ $file (have it)"
    continue
  fi
  echo "↓ $file"
  touch "$DEST/$file.part"
  # Short timeouts so a dead mirror fails fast; if the default attempt fails, retry IPv4-only
  # (some networks hang on IPv6), still resuming the partial file.
  WGET=(wget -nv -c --connect-timeout=20 --read-timeout=30 --tries=3 --waitretry=5 -O "$DEST/$file")
  if "${WGET[@]}" "$MIRROR/$path" || { echo "retrying over IPv4 only"; "${WGET[@]}" -4 "$MIRROR/$path"; }; then
    rm -f "$DEST/$file.part"
  else
    echo "✗ failed: $file (re-run to resume)" >&2
  fi
done

# Rebuild the Kiwix library index so kiwix-serve picks up every ZIM.
if command -v kiwix-manage >/dev/null; then
  rm -f "$DEST/library.xml"
  for z in "$DEST"/*.zim; do
    [[ -f "$z.part" ]] && continue
    kiwix-manage "$DEST/library.xml" add "$z"
  done
  echo "Library index: $DEST/library.xml"
fi
echo "Done. Total: $(du -sh "$DEST" | cut -f1)"
