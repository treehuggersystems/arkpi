#!/usr/bin/env python3
"""Download ARK·π's public-domain Books & Media library.

    python3 scripts/fetch-media.py [dest]        (default: /opt/offline-data/media)

Reads scripts/media-catalog.json. Resumable: finished items are skipped.
  books/<gutenberg-id>/   HTML edition (with images) + .epub for phone readers
  audio/<ia-id>/          LibriVox 64 kbps MP3 chapters
  video/<ia-id>.mp4       Internet Archive public-domain films
Writes library.json, which the /media page reads.
"""
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / "media-catalog.json").read_text())
DEST = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/offline-data/media")
UA = {"User-Agent": "ARK-pi-offline-library/1.0 (personal offline archive)"}


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url: str, path: Path):
    """Stream to a .part file, then rename, so interrupted downloads are retried."""
    if path.exists():
        return
    tmp = path.with_name(path.name + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(path)


def fetch_books(lib: list):
    for b in CATALOG["books"]:
        d = DEST / "books" / str(b["id"])
        entry = {**b, "kind": "book", "path": f"books/{b['id']}"}
        if (d / "index.html").exists():
            lib.append({**entry, "epub": (d / "book.epub").exists()})
            continue
        print(f"book  {b['id']:>6}  {b['title']}")
        try:
            d.mkdir(parents=True, exist_ok=True)
            z = zipfile.ZipFile(io.BytesIO(get(f"https://www.gutenberg.org/cache/epub/{b['id']}/pg{b['id']}-h.zip")))
            names = [n for n in z.namelist() if not n.endswith("/")]
            # Older zips wrap everything in one "<id>-h/" folder; newer ones don't. Only strip a
            # wrapper folder that contains the HTML (never "images/").
            tops = {Path(n).parts[0] for n in names}
            strip = len(tops) == 1 and len(Path(names[0]).parts) > 1 and any(
                n.lower().endswith((".htm", ".html")) and len(Path(n).parts) == 2 for n in names)
            for name in names:
                rel = Path(*Path(name).parts[1:]) if strip else Path(name)
                if not str(rel) or ".." in rel.parts:
                    continue
                out = d / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(name))
            html = sorted(d.glob("*.htm*"), key=lambda p: p.stat().st_size, reverse=True)
            if html and html[0].name != "index.html":
                html[0].rename(d / "index.html")
            try:
                download(f"https://www.gutenberg.org/ebooks/{b['id']}.epub3.images", d / "book.epub")
            except Exception:
                pass
            lib.append({**entry, "epub": (d / "book.epub").exists()})
        except Exception as e:
            print(f"   ✗ {e}")
        time.sleep(2)  # be polite to Project Gutenberg


def fetch_audio(lib: list):
    for a in CATALOG["audio"]:
        d = DEST / "audio" / a["ia"]
        try:
            meta = json.loads(get(f"https://archive.org/metadata/{a['ia']}", 60))
        except Exception as e:
            print(f"   ✗ {a['ia']}: {e}")
            continue
        tracks = sorted((f for f in meta["files"] if f["name"].endswith("_64kb.mp3")), key=lambda f: f["name"])
        d.mkdir(parents=True, exist_ok=True)
        print(f"audio {a['title']} ({len(tracks)} tracks)")
        done = []
        for t in tracks:
            path = d / Path(t["name"]).name
            try:
                download(f"https://archive.org/download/{a['ia']}/{urllib.request.quote(t['name'])}", path)
                done.append({"file": path.name, "title": t.get("title") or path.stem})
            except Exception as e:
                print(f"   ✗ {t['name']}: {e}")
        lib.append({**a, "kind": "audio", "path": f"audio/{a['ia']}", "tracks": done})


def fetch_video(lib: list):
    (DEST / "video").mkdir(parents=True, exist_ok=True)
    for v in CATALOG["video"]:
        path = DEST / "video" / f"{v['ia']}.mp4"
        print(f"video {v['title']}")
        try:
            download(f"https://archive.org/download/{v['ia']}/{urllib.request.quote(v['file'])}", path)
            lib.append({**v, "kind": "video", "path": f"video/{path.name}", "size": path.stat().st_size})
        except Exception as e:
            print(f"   ✗ {e}")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    which = set(sys.argv[2:]) or {"books", "audio", "video"}
    lib: list = []
    old = {}
    try:
        old = {(i["kind"], str(i.get("id") or i.get("ia"))): i for i in json.loads((DEST / "library.json").read_text())}
    except (OSError, ValueError):
        pass
    if "books" in which:
        fetch_books(lib)
    if "audio" in which:
        fetch_audio(lib)
    if "video" in which:
        fetch_video(lib)
    # Keep entries for kinds we didn't fetch this run.
    merged = {(i["kind"], str(i.get("id") or i.get("ia"))): i for i in lib}
    for k, i in old.items():
        if i["kind"] not in which:
            merged.setdefault(k, i)
    (DEST / "library.json").write_text(json.dumps(list(merged.values()), indent=1, ensure_ascii=False))
    print(f"Done: {len(merged)} items → {DEST / 'library.json'}")


if __name__ == "__main__":
    main()
