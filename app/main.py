"""ARK·π — The Pocket Ark: an offline knowledge server for a Raspberry Pi.

A small, dependency-light knowledge base meant to run with zero internet:
markdown files with YAML front matter in ``content/<category>/``, PDF manuals
in ``MANUALS_DIR``, and an optional Kiwix server for offline Wikipedia.
"""

import json
import os
import re
import socket
import threading
import urllib.error
import urllib.request
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import markdown
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import bible

# ----------------------
# CONFIG
# ----------------------
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
CONTENT_DIR = Path(os.environ.get("OFFLINE_CONTENT_DIR", BASE_DIR.parent / "content"))
DATA_DIR = Path(os.environ.get("OFFLINE_DATA_DIR", BASE_DIR.parent / "data"))
MANUALS_DIR = Path(os.environ.get("OFFLINE_MANUALS_DIR", "/opt/offline-data/manuals"))
MAPS_DIR = Path(os.environ.get("OFFLINE_MAPS_DIR", "/opt/offline-data/maps"))
MEDIA_DIR = Path(os.environ.get("OFFLINE_MEDIA_DIR", "/opt/offline-data/media"))
KIWIX_PORT = int(os.environ.get("KIWIX_PORT", "8082"))                # where kiwix-serve listens (internal)
KIWIX_PUBLIC_PORT = int(os.environ.get("KIWIX_PUBLIC_PORT", "8081"))  # nginx port for plain-HTTP links
KIWIX_HOST = os.environ.get("KIWIX_HOST", "127.0.0.1")
KIWIX_ROOT = "/" + os.environ.get("KIWIX_ROOT", "/kiwix").strip("/")  # kiwix-serve --urlRootLocation

CRITICAL_TAGS = {"emergency", "medical", "danger"}
HAZARD_TAGS = {"danger", "lye", "bleeding", "fire"}
PRIORITY_TAGS = {"emergency", "medical"}

# Display info for known categories; unknown folders still work with defaults.
CATEGORY_META = {
    "faith":      {"label": "Faith",         "icon": "cross",   "blurb": "Scripture, prayer, the Gospel, church without a building, and comfort in hard times."},
    "medical":    {"label": "Medical",       "icon": "medical", "blurb": "Trauma, first aid, illness and injury care."},
    "water":      {"label": "Water",         "icon": "water",   "blurb": "Finding, purifying and storing safe water."},
    "comms":      {"label": "Comms",         "icon": "radio",   "blurb": "Radio frequencies, procedures, signals and codes."},
    "recipes":    {"label": "Recipes",       "icon": "bread",   "blurb": "Tested, refined, from-scratch kitchen recipes."},
    "food":       {"label": "Food & Preserving", "icon": "jar", "blurb": "Canning, freezing, drying, pickling, storage life and cooking without power."},
    "power":      {"label": "Power & EMP",   "icon": "bolt",    "blurb": "EMP protection, batteries, solar and generators."},
    "repair":     {"label": "Fix-It",        "icon": "wrench",  "blurb": "Repair guides for engines, plumbing, vehicles and gear."},
    "navigation": {"label": "Navigation",    "icon": "compass", "blurb": "Map, compass, and finding direction without either."},
    "fieldcraft": {"label": "Fieldcraft",    "icon": "footprint", "blurb": "Tracking, orienteering, stars, weather lore, fire by friction, and living off the land."},
    "shelter":    {"label": "Shelter",       "icon": "tent",    "blurb": "Staying warm, dry and protected. Knots and cordage."},
    "tech":       {"label": "Pi & Tech",     "icon": "chip",    "blurb": "Raspberry Pi, Linux, Python, electronics, sensors, radio and mesh — and keeping software working offline."},
    "homestead":  {"label": "Homestead",     "icon": "home",    "blurb": "Fire, soap, sanitation and self-reliance skills."},
    "plants":     {"label": "Plants",        "icon": "leaf",    "blurb": "Foraging, gardening and seed saving."},
}
CATEGORY_ORDER = list(CATEGORY_META)

SAFE_NAME = re.compile(r"^[\w\- ().,'&]+$")

app = FastAPI(title="ARK·π — The Pocket Ark")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ----------------------
# CONTENT INDEX
# ----------------------
def parse_doc(filepath: Path, category: str) -> dict:
    raw = filepath.read_text(encoding="utf-8")
    metadata, body = {}, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                metadata = {}
            body = parts[2]

    name = filepath.stem
    title = metadata.get("title") or _title_from_body(body) or name
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags = [str(t) for t in tags]

    return {
        "name": name,
        "category": category,
        "title": str(title),
        "tags": tags,
        "summary": metadata.get("summary") or _summary_from_body(body),
        "metadata": metadata,
        "body": body,
        "mtime": filepath.stat().st_mtime,
        "critical": bool(CRITICAL_TAGS & set(tags)),
    }


def _title_from_body(body: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def _summary_from_body(body: str) -> str:
    """Intro paragraph between the H1 and the first section, if there is one."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("## "):
            break
        if not line or line.startswith(("#", "-", "*", "|", ">", "---", "http")) or re.match(r"\d+\.", line) or line.endswith(":"):
            continue
        text = re.sub(r"[*_`]", "", line)
        return text if len(text) <= 180 else text[:177].rsplit(" ", 1)[0] + "…"
    return ""


class ContentIndex:
    """Scans the content dir, re-scanning only when files change."""

    def __init__(self, root: Path):
        self.root = root
        self._sig = None
        self._docs: list[dict] = []
        self._lock = threading.Lock()

    def _signature(self):
        sig = []
        if not self.root.exists():
            return ()
        for cat in sorted(self.root.iterdir()):
            if not cat.is_dir() or cat.name.startswith((".", "_")):
                continue
            sig.append((cat.name, cat.stat().st_mtime))
            for f in sorted(cat.glob("*.md")):
                sig.append((f.name, f.stat().st_mtime))
        return tuple(sig)

    def docs(self) -> list[dict]:
        sig = self._signature()
        if sig != self._sig:
            with self._lock:
                docs = []
                for cat in self.root.iterdir():
                    if not cat.is_dir() or cat.name.startswith((".", "_")):
                        continue
                    for f in cat.glob("*.md"):
                        try:
                            docs.append(parse_doc(f, cat.name))
                        except (OSError, UnicodeDecodeError):
                            continue
                docs.sort(key=lambda d: d["title"].lower())
                self._docs, self._sig = docs, sig
        return self._docs

    def categories(self) -> list[dict]:
        counts: dict[str, int] = {}
        for d in self.docs():
            counts[d["category"]] = counts.get(d["category"], 0) + 1
        if self.root.exists():
            for cat in self.root.iterdir():
                if cat.is_dir() and not cat.name.startswith((".", "_")):
                    counts.setdefault(cat.name, 0)
        names = sorted(counts, key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99, c))
        return [category_info(n, counts[n]) for n in names]

    def get(self, category: str, name: str):
        for d in self.docs():
            if d["category"] == category and d["name"] == name:
                return d
        return None

    def in_category(self, category: str) -> list[dict]:
        return [d for d in self.docs() if d["category"] == category]


def category_info(name: str, count: int = 0) -> dict:
    meta = CATEGORY_META.get(name, {})
    return {
        "name": name,
        "label": meta.get("label", name.replace("_", " ").title()),
        "icon": meta.get("icon", "book"),
        "blurb": meta.get("blurb", ""),
        "count": count,
    }


index = ContentIndex(CONTENT_DIR)


# ----------------------
# RENDERING HELPERS
# ----------------------
CANNING_FILE = STATIC_DIR / "data" / "canning.json"
CANNING_EMBED = re.compile(r"^\[\[canning:(\w+)\]\]\s*$", re.M)


def _canning_tables(body: str) -> str:
    """[[canning:vegetables]] -> USDA processing-time table from static/data/canning.json."""
    if "[[canning:" not in body:
        return body
    data = json.loads(CANNING_FILE.read_text())
    def repl(m):
        rows = [f for f in data["foods"] if f["group"] == m.group(1)]
        if not rows:
            return m.group(0)
        out = ["| Food | Method | Pints | Quarts | Headspace |", "|---|---|---|---|---|"]
        for f in rows:
            method = "Pressure" if f["method"] == "pressure" else "Water bath" + (" + acid" if f.get("acid") else "")
            q = f"{f['quart']} min" if f.get("quart") else "—"
            out.append(f"| {f['name']} | {method} | {f['pint']} min | {q} | {f['headspace']} |")
        return "\n".join(out)
    return CANNING_EMBED.sub(repl, body)


LIST_AFTER_TEXT = re.compile(r"^((?![ \t]*(?:[-*+]|\d+\.)[ \t]).*\S.*)\n([ \t]*(?:[-*+]|\d+\.)[ \t])", re.M)

NESTED_2SP = re.compile(r"^((?:  )+)(?<!    )([-*+] |\d+\. )", re.M)


def render_markdown(body: str, scripture_links: bool = False, tr: str = bible.DEFAULT_TR) -> tuple[str, list]:
    # Let a list start right after a line of text ("Add:\n- Flour"), as most
    # markdown editors do. Only affects rendering; files are never modified.
    body = LIST_AFTER_TEXT.sub(r"\1\n\n\2", body)
    # Nested lists indented by 2 spaces -> 4 (Python-Markdown needs 4).
    body = NESTED_2SP.sub(lambda m: " " * (len(m.group(1)) * 2) + m.group(2), body)
    body = _canning_tables(body)          # [[canning:group]] -> USDA table
    body = bible.expand_embeds(body, tr)  # [[John 3:16]] -> verse text
    exts = ["extra", "sane_lists", "toc"] + (["nl2br"] if scripture_links else [])  # keep hymn/poetry line breaks
    md = markdown.Markdown(extensions=exts,
                           extension_configs={"toc": {"permalink": False}})
    html = md.convert(body)
    if scripture_links:
        html = bible.link_refs_html(html)
    return html, md.toc_tokens


def split_recipe(html: str) -> dict:
    """Split rendered recipe HTML into side panels (ingredients etc.) and main body.

    Only re-arranges existing HTML by <h2> section; the recipe text itself is untouched.
    """
    side_keys = ("ingredients", "equipment", "yield")
    parts = re.split(r"(?=<h2[^>]*>)", html)
    intro, side, main = [], [], []
    for part in parts:
        m = re.match(r"<h2[^>]*>(.*?)</h2>", part, re.S)
        if not m:
            intro.append(part)
            continue
        heading = re.sub(r"<[^>]+>", "", m.group(1)).strip().lower()
        (side if any(heading.startswith(k) for k in side_keys) else main).append(part)
    # Drop the H1 from the intro; the template renders the title itself.
    intro_html = re.sub(r"<h1[^>]*>.*?</h1>", "", "".join(intro), count=1, flags=re.S)
    return {"intro": intro_html, "side": "".join(side), "main": "".join(main)}


_kiwix_cache = {"t": 0.0, "books": []}


def kiwix_books() -> list[dict]:
    """Books served by kiwix-serve, read from its OPDS catalog (cached 5 min)."""
    import time
    import urllib.request
    import xml.etree.ElementTree as ET
    if time.time() - _kiwix_cache["t"] < 300:
        return _kiwix_cache["books"]
    books = []
    try:
        url = f"http://{KIWIX_HOST}:{KIWIX_PORT}{KIWIX_ROOT.rstrip('/')}/catalog/v2/entries?count=500"
        with urllib.request.urlopen(url, timeout=1.5) as r:
            root = ET.fromstring(r.read())
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns):
            href = next((l.get("href") for l in e.findall("a:link", ns) if l.get("type") == "text/html"), None)
            if not href:
                continue
            books.append({
                "title": e.findtext("a:title", "", ns),
                "summary": e.findtext("a:summary", "", ns),
                "href": href[len(KIWIX_ROOT):].lstrip("/") if href.startswith(KIWIX_ROOT) else href.lstrip("/"),
                "articles": int(e.findtext("a:articleCount", "0", ns) or 0),
            })
        books.sort(key=lambda b: b["title"].lower())
    except Exception:
        books = []
    _kiwix_cache.update(t=time.time(), books=books)
    return books


def kiwix_search(query: str, limit: int = 8) -> dict:
    """Full-text search across every Kiwix book; returns {"total", "results": [...]}."""
    import html as htmllib
    import urllib.parse
    import urllib.request
    try:
        url = (f"http://{KIWIX_HOST}:{KIWIX_PORT}{KIWIX_ROOT.rstrip('/')}/search?"
               + urllib.parse.urlencode({"pattern": query, "pageLength": limit}))
        with urllib.request.urlopen(url, timeout=4) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception:
        return {"total": 0, "results": []}
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    m = re.search(r"Results ([\d,]+) ?- ?([\d,]+) of ([\d,]+)", text)
    total = int(m.group(3).replace(",", "")) if m else 0
    results = []
    for li in re.findall(r"<li>(.*?)</li>", page, re.S):
        a = re.search(r'<a href="([^"]+)">\s*(.*?)\s*</a>', li, re.S)
        if not a:
            continue
        cite = re.search(r"<cite>(.*?)</cite>", li, re.S)
        book = re.search(r'class="book-title">\s*(?:from\s*)?(.*?)\s*</div>', li, re.S)
        clean = lambda x: htmllib.unescape(re.sub(r"<[^>]+>", "", x or "")).strip()
        href = a.group(1)
        if href.startswith(KIWIX_ROOT):
            href = href[len(KIWIX_ROOT):].lstrip("/")
        results.append({"href": href, "title": clean(a.group(2)),
                        "snippet": clean(cite.group(1) if cite else "")[:220],
                        "book": clean(book.group(1) if book else "")})
    return {"total": total or len(results), "results": results[:limit]}


def kiwix_status(request: Request) -> dict:
    up = False
    try:
        with socket.create_connection((KIWIX_HOST, KIWIX_PORT), timeout=0.3):
            up = True
    except OSError:
        pass
    # Same origin as ARK itself: served by kiwix_proxy (or nginx's /kiwix/ on HTTPS).
    return {"up": up, "url": KIWIX_ROOT.rstrip("/") + "/"}


_static_v = {"t": 0.0, "v": "0"}


def static_version() -> str:
    """Cache-busting token for our own CSS/JS: changes whenever any static file changes."""
    import time
    if time.time() - _static_v["t"] > 5:
        newest = max((p.stat().st_mtime for p in STATIC_DIR.glob("*.*")), default=0)
        _static_v.update(t=time.time(), v=str(int(newest)))
    return _static_v["v"]


def render(template: str, request: Request, status_code: int = 200, **ctx) -> HTMLResponse:
    ctx.setdefault("v", static_version())
    ctx.setdefault("nav_categories", index.categories())
    ctx.setdefault("path", request.url.path)
    return HTMLResponse(env.get_template(template).render(**ctx), status_code=status_code)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ----------------------
# HOME
# ----------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    docs = index.docs()
    recent = sorted(docs, key=lambda d: d["mtime"], reverse=True)[:6]
    quick = [index.get(c, n) for c, n in [
        ("medical", "bleeding_control"), ("medical", "cpr_adult"),
        ("water", "water_purification_methods"), ("comms", "emergency_frequencies"),
        ("medical", "burns"), ("power", "emp_faraday_protection"),
    ]]
    return render("home.html", request,
                  votd=bible.verse_of_the_day(bible_tr(request)),
                  categories=index.categories(),
                  quick=[q for q in quick if q],
                  recent=recent,
                  total=len(docs),
                  manual_count=len(list_manuals()),
                  map_layers=map_layers(),
                  kiwix=kiwix_status(request),
                  quick_tags=["hygiene", "medical", "water", "emergency"])


# ----------------------
# SEARCH
# ----------------------
@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    query = q.strip()
    results = []
    if query:
        terms = query.lower().split()
        for d in index.docs():
            title = d["title"].lower()
            hay = f"{title} {' '.join(d['tags']).lower()} {d['body'].lower()}"
            if all(t in hay for t in terms):
                score = sum(3 for t in terms if t in title) + sum(2 for t in terms if t in d["tags"])
                results.append((score, _snippet(d["body"], terms[0]), d))
        results.sort(key=lambda r: (-r[0], r[2]["title"].lower()))
    kiwix = kiwix_status(request)
    wiki = kiwix_search(query) if (query and kiwix["up"]) else {"total": 0, "results": []}
    return render("search.html", request, query=query,
                  results=[{**d, "snippet": s} for _, s, d in results],
                  kiwix=kiwix, wiki=wiki)


def _snippet(body: str, term: str, width: int = 90) -> str:
    text = re.sub(r"[#*_`>|]", "", body)
    text = re.sub(r"\s+", " ", text)
    i = text.lower().find(term)
    if i < 0:
        return text[: width * 2].strip()
    start = max(0, i - width)
    return ("…" if start else "") + text[start:i + width].strip() + "…"


# ----------------------
# TAGS & CRITICAL
# ----------------------
@app.get("/tag/{tag}", response_class=HTMLResponse)
def tag_view(request: Request, tag: str):
    results = [d for d in index.docs() if tag in d["tags"]]
    return render("list.html", request, heading=f"#{tag}", eyebrow="Tag",
                  results=results, empty="No entries found for this tag.")


@app.get("/critical", response_class=HTMLResponse)
def critical(request: Request):
    results = [d for d in index.docs() if d["critical"]]
    results.sort(key=lambda d: (d["category"] != "medical", d["title"].lower()))
    return render("list.html", request, heading="Critical Information", eyebrow="Priority",
                  results=results, critical=True,
                  intro="Life-safety references. Read these before you need them.")


@app.get("/tags", response_class=HTMLResponse)
def all_tags(request: Request):
    counts: dict[str, int] = {}
    for d in index.docs():
        for t in d["tags"]:
            counts[t] = counts.get(t, 0) + 1
    return render("tags.html", request, tags=sorted(counts.items()))


# ----------------------
# MANUAL LIBRARY
# ----------------------
# Friendly names for well-known public-domain manuals, keyed by lowercase filename.
MANUAL_TITLES = {
    "fm3-05-70.pdf":       ("FM 3-05.70", "Survival", "survival"),
    "fm4-25-11.pdf":       ("FM 4-25.11", "First Aid", "medical"),
    "fm_5_34.pdf":         ("FM 5-34", "Engineer Field Data", "engineering"),
    "fm5-34.pdf":          ("FM 5-34", "Engineer Field Data", "engineering"),
    "ranger_handbook.pdf": ("SH 21-76", "Ranger Handbook", "field craft"),
    "tm31-210.pdf":        ("TM 31-210", "Improvised Munitions Handbook", "reference"),
    "fm21-76.pdf":         ("FM 21-76", "Survival (1992)", "survival"),
    "fm3-25-26.pdf":       ("FM 3-25.26", "Map Reading & Land Navigation", "navigation"),
    "fm21-11.pdf":         ("FM 21-11", "First Aid for Soldiers", "medical"),
}


def _is_valid_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def list_manuals() -> list[dict]:
    if not MANUALS_DIR.is_dir():
        return []
    manuals = []
    for p in sorted(MANUALS_DIR.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        is_pdf = p.suffix.lower() == ".pdf"
        if is_pdf and not _is_valid_pdf(p):
            continue  # e.g. a saved 404 page renamed .pdf
        code, title, kind = MANUAL_TITLES.get(
            p.name.lower(), ("", p.stem.replace("_", " ").replace("-", " ").title(), p.suffix.lstrip(".").lower()))
        manuals.append({"file": p.name, "code": code, "title": title, "kind": kind,
                        "size": human_size(p.stat().st_size)})
    # Collapse duplicates of the same manual (keep the first valid one).
    seen, unique = set(), []
    for m in manuals:
        key = (m["code"], m["title"])
        if m["code"] and key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_kiwix_opener = urllib.request.build_opener(_NoRedirect)
_HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "content-length", "server", "date"}


@app.api_route("/kiwix", methods=["GET", "HEAD"])
@app.api_route("/kiwix/{rest:path}", methods=["GET", "HEAD"])
def kiwix_proxy(request: Request, rest: str = ""):
    """Serve kiwix-serve through ARK's own port, so the libraries work on whatever address
    reaches ARK (no extra port to open in firewalls)."""
    url = f"http://{KIWIX_HOST}:{KIWIX_PORT}{KIWIX_ROOT.rstrip('/')}/{quote(rest, safe='/:@!$&()*+,;=-._~')}"
    if request.url.query:
        url += "?" + request.url.query
    fwd = {k: v for k, v in request.headers.items() if k.lower() in ("range", "accept", "accept-encoding", "accept-language", "if-none-match", "if-modified-since")}
    try:
        upstream = _kiwix_opener.open(urllib.request.Request(url, headers=fwd, method=request.method), timeout=30)
    except urllib.error.HTTPError as e:
        upstream = e  # 3xx/4xx/5xx: pass through status, headers and body
    except OSError:
        return render("404.html", request, status_code=502)
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_HEADERS}
    loc = headers.get("Location") or headers.get("location")
    if loc and loc.startswith(f"http://{KIWIX_HOST}:{KIWIX_PORT}"):
        headers["Location"] = loc[len(f"http://{KIWIX_HOST}:{KIWIX_PORT}"):]

    def body():
        try:
            while chunk := upstream.read(64 * 1024):
                yield chunk
        finally:
            upstream.close()
    return StreamingResponse(body(), status_code=upstream.status if hasattr(upstream, "status") else upstream.code,
                             headers=headers)


@app.get("/library", response_class=HTMLResponse)
def library(request: Request):
    kiwix = kiwix_status(request)
    return render("library.html", request, manuals=list_manuals(),
                  manuals_dir=str(MANUALS_DIR), kiwix=kiwix,
                  books=kiwix_books() if kiwix["up"] else [])


@app.get("/manual/{filename}")
def get_manual(filename: str):
    path = (MANUALS_DIR / filename).resolve()
    if path.parent != MANUALS_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Manual not found")
    return FileResponse(path, content_disposition_type="inline")


# ----------------------
# BOOKS & MEDIA
# ----------------------
MEDIA_CATALOG = BASE_DIR.parent / "scripts" / "media-catalog.json"


def media_library() -> list[dict]:
    """Everything from the media catalog that's already on disk, so the page fills in
    while scripts/fetch-media.py is still downloading."""
    try:
        catalog = json.loads(MEDIA_CATALOG.read_text())
    except (OSError, ValueError):
        return []
    items = []
    for b in catalog.get("books", []):
        d = MEDIA_DIR / "books" / str(b["id"])
        if (d / "index.html").is_file():
            items.append({**b, "kind": "book", "path": f"books/{b['id']}", "epub": (d / "book.epub").is_file()})
    for a in catalog.get("audio", []):
        d = MEDIA_DIR / "audio" / a["ia"]
        tracks = sorted(d.glob("*.mp3")) if d.is_dir() else []
        if tracks:
            items.append({**a, "kind": "audio", "path": f"audio/{a['ia']}",
                          "tracks": [{"file": t.name, "title": _track_title(t.stem)} for t in tracks]})
    for v in catalog.get("video", []):
        f = MEDIA_DIR / "video" / f"{v['ia']}.mp4"
        if f.is_file():
            items.append({**v, "kind": "video", "path": f"video/{f.name}", "size": f.stat().st_size})
    return items


def _track_title(stem: str) -> str:
    """'treasureisland_03_stevenson_64kb' -> 'Part 3'."""
    m = re.search(r"_(\d{1,3})_", stem + "_")
    return f"Part {int(m.group(1))}" if m else stem.replace("_64kb", "").replace("_", " ")


def _media_path(rel: str) -> Path:
    path = (MEDIA_DIR / rel).resolve()
    if not str(path).startswith(str(MEDIA_DIR.resolve()) + os.sep) or not path.is_file():
        raise HTTPException(404)
    return path


@app.get("/media", response_class=HTMLResponse)
def media_index(request: Request, kind: str = "book"):
    items = media_library()
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in ("book", "audio", "video")}
    kind = kind if kind in counts else "book"
    shelves: dict[str, list] = {}
    for i in items:
        if i["kind"] == kind:
            shelves.setdefault(i.get("shelf", "Other"), []).append(i)
    return render("media/index.html", request, kind=kind, counts=counts, shelves=shelves)


@app.get("/media/books/{book_id}/{rest:path}")
def media_book(request: Request, book_id: int, rest: str = ""):
    base = MEDIA_DIR / "books" / str(book_id)
    if rest in ("", "index.html"):
        page = base / "index.html"
        if not page.is_file():
            return render("404.html", request, status_code=404)
        html = page.read_text(encoding="utf-8", errors="replace")
        meta = next((i for i in media_library() if i["kind"] == "book" and i.get("id") == book_id), {})
        bar = (f'<div id="ark-bar"><a href="/media">← Library</a><span>{meta.get("title", "")}</span>'
               f'{"<a href=book.epub download>EPUB</a>" if meta.get("epub") else ""}</div>')
        inject = ('<script>try{document.documentElement.dataset.theme=localStorage.getItem("theme")||"dark"}catch(e){}</script>'
                  '<link rel="stylesheet" href="/static/reader.css">')
        html = re.sub(r"(</head>)", inject + r"\1", html, count=1, flags=re.I)
        html = re.sub(r"(<body[^>]*>)", r"\1" + bar, html, count=1, flags=re.I)
        html = re.sub(r"<img\b(?![^>]*\bloading=)", '<img loading="lazy" decoding="async"', html, flags=re.I)  # big illustrated books
        if not rest:
            return RedirectResponse(f"/media/books/{book_id}/index.html", status_code=302)
        return HTMLResponse(html)
    return FileResponse(_media_path(f"books/{book_id}/{rest}"))


@app.get("/media/file/{rel:path}")
def media_file(rel: str):
    return FileResponse(_media_path(rel))  # supports Range (seeking in audio/video)


@app.get("/media/watch/{ia}", response_class=HTMLResponse)
def media_watch(request: Request, ia: str):
    item = next((i for i in media_library() if i["kind"] == "video" and i["ia"] == ia), None)
    if not item:
        return render("404.html", request, status_code=404)
    return render("media/watch.html", request, item=item)


@app.get("/media/listen/{ia}", response_class=HTMLResponse)
def media_listen(request: Request, ia: str):
    item = next((i for i in media_library() if i["kind"] == "audio" and i["ia"] == ia), None)
    if not item:
        return render("404.html", request, status_code=404)
    return render("media/listen.html", request, item=item)


# ----------------------
# OFFLINE MAP
# ----------------------
def map_layers() -> list[dict]:
    layers = []
    try:
        layers = json.loads((MAPS_DIR / "layers.json").read_text())
    except (OSError, ValueError):
        # No manifest: show any .pmtiles present, biggest last (assumed most detailed).
        files = sorted(MAPS_DIR.glob("*.pmtiles"), key=lambda p: p.stat().st_size) if MAPS_DIR.is_dir() else []
        layers = [{"file": f.name, "name": f.stem.title(), "minzoom": 0, "maxzoom": 15} for f in files]
    out = []
    for layer in layers:
        f = MAPS_DIR / layer.get("file", "")
        if f.is_file() and f.suffix == ".pmtiles":
            out.append({**layer, "url": f"/maps/{f.name}", "size": human_size(f.stat().st_size)})
    return out


@app.get("/map", response_class=HTMLResponse)
def offline_map(request: Request):
    return render("map.html", request, layers=map_layers())


@app.get("/maps/{filename}")
def map_file(filename: str):
    path = (MAPS_DIR / filename).resolve()
    if path.parent != MAPS_DIR.resolve() or path.suffix != ".pmtiles" or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/octet-stream")  # supports Range requests


# ----------------------
# TOOLS
# ----------------------
TOOLS = [
    ("water",     "Water Planner",        "How much water you need to store, per person and per day.", "water"),
    ("bleach",    "Bleach Dosing",        "Drops of household bleach to disinfect any volume of water.", "drop"),
    ("canning",   "Canning Lookup",       "USDA method, pressure, time and headspace for any food, jar and altitude.", "jar"),
    ("food",      "Food Storage Planner", "Calories, rice, beans and oil for your household and timeline.", "box"),
    ("baker",     "Recipe Scaler",        "Scale gram-based recipes and see baker's percentages.", "bread"),
    ("power",     "Battery & Solar",      "Size a battery bank and solar array for your loads.", "bolt"),
    ("generator", "Generator Fuel",       "Fuel needed to run a generator for a given time.", "fuel"),
    ("radio",     "Antenna & Ohm's Law",  "Dipole / quarter-wave lengths and Ohm's law solver.", "radio"),
    ("morse",     "Morse Code",           "Translate text to Morse and back, with audio and light.", "signal"),
    ("sun",       "Sun & Moon",           "Sunrise, sunset, daylight and moon phase — fully offline.", "sun"),
    ("convert",   "Unit Converter",       "Length, weight, volume, temperature, cooking measures.", "scale"),
    ("weather",   "Wind Chill & Heat",    "Wind chill, heat index and dew point danger levels.", "thermo"),
    ("timers",    "Timers",               "Multiple named countdown timers for the kitchen or the field.", "clock"),
    ("pantry",    "Pantry Inventory",     "Track stored food and supplies with expiration dates.", "box"),
    ("checklists", "Kit Checklists",      "Go-bag, 72-hour, vehicle, medical and comms kits, shared across devices.", "check"),
    ("logbook",   "Logbook",              "Timestamped event, radio contact and incident log.", "file"),
]
TOOL_MAP = {t[0]: t for t in TOOLS}


@app.get("/tools", response_class=HTMLResponse)
def tools_index(request: Request):
    return render("tools.html", request, tools=TOOLS)


@app.get("/tools/{tool}", response_class=HTMLResponse)
def tool_page(request: Request, tool: str):
    if tool not in TOOL_MAP:
        raise HTTPException(404)
    slug, title, blurb, icon = TOOL_MAP[tool]
    return render(f"tools/{slug}.html", request, tool={"slug": slug, "title": title, "blurb": blurb, "icon": icon},
                  tools=TOOLS)


# --- Small JSON stores (persisted server-side so every device sees the same data)
_store_lock = threading.Lock()


def _load_store(name: str) -> list:
    try:
        return json.loads((DATA_DIR / f"{name}.json").read_text())
    except (OSError, ValueError):
        return []


def _save_store(name: str, items: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=2))
    tmp.replace(path)


def _upsert(store: str, item: dict) -> dict:
    with _store_lock:
        items = [i for i in _load_store(store) if i.get("id") != item["id"]]
        items.append(item)
        _save_store(store, items)
    return item


def _delete(store: str, item_id: str) -> None:
    with _store_lock:
        _save_store(store, [i for i in _load_store(store) if i.get("id") != item_id])


@app.get("/api/pantry")
def pantry_list():
    return JSONResponse(_load_store("pantry"))


@app.post("/api/pantry")
async def pantry_upsert(request: Request):
    data = await request.json()
    item = {
        "id": str(data.get("id") or uuid.uuid4().hex[:10]),
        "name": str(data.get("name", "")).strip()[:120],
        "qty": str(data.get("qty", "")).strip()[:40],
        "location": str(data.get("location", "")).strip()[:60],
        "expires": str(data.get("expires", "")).strip()[:10],
        "notes": str(data.get("notes", "")).strip()[:300],
        "updated": date.today().isoformat(),
    }
    if not item["name"]:
        raise HTTPException(400, "name required")
    return JSONResponse(_upsert("pantry", item))


@app.delete("/api/pantry/{item_id}")
def pantry_delete(item_id: str):
    _delete("pantry", item_id)
    return JSONResponse({"ok": True})


# --- Shared key/value state (checklist check-offs etc.)
@app.get("/api/state/{key}")
def state_get(key: str):
    if not re.fullmatch(r"[a-z0-9_\-]{1,40}", key):
        raise HTTPException(400)
    try:
        return JSONResponse(json.loads((DATA_DIR / f"state-{key}.json").read_text()))
    except (OSError, ValueError):
        return JSONResponse({})


@app.post("/api/state/{key}")
async def state_set(key: str, request: Request):
    if not re.fullmatch(r"[a-z0-9_\-]{1,40}", key):
        raise HTTPException(400)
    data = await request.json()
    if not isinstance(data, dict) or len(json.dumps(data)) > 200_000:
        raise HTTPException(400)
    with _store_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / f"state-{key}.json").write_text(json.dumps(data))
    return JSONResponse({"ok": True})


# --- Logbook
@app.get("/api/log")
def log_list():
    return JSONResponse(sorted(_load_store("logbook"), key=lambda e: e.get("ts", ""), reverse=True))


@app.post("/api/log")
async def log_add(request: Request):
    data = await request.json()
    text = str(data.get("text", "")).strip()[:2000]
    if not text:
        raise HTTPException(400, "text required")
    item = {
        "id": uuid.uuid4().hex[:10],
        "ts": str(data.get("ts") or "")[:25],
        "kind": str(data.get("kind", "note"))[:20],
        "callsign": str(data.get("callsign", "")).strip()[:20],
        "freq": str(data.get("freq", "")).strip()[:20],
        "text": text,
    }
    return JSONResponse(_upsert("logbook", item))


@app.delete("/api/log/{item_id}")
def log_delete(item_id: str):
    _delete("logbook", item_id)
    return JSONResponse({"ok": True})


# --- Recipe ingredients for the scaler (read-only view of the recipe files)
@app.get("/api/recipes")
def recipe_ingredients():
    out = []
    for d in index.in_category("recipes"):
        items, in_ing = [], False
        for line in d["body"].splitlines():
            if line.startswith("## "):
                in_ing = line[3:].strip().lower().startswith("ingredients")
                continue
            if in_ing and line.lstrip().startswith(("- ", "* ")):
                items.append(line.strip()[2:].strip())
        if items:
            out.append({"name": d["name"], "title": d["title"], "ingredients": items})
    return JSONResponse(out)


# --- Map waypoints (rally points, caches, water sources…)
@app.get("/api/waypoints")
def waypoint_list():
    return JSONResponse(_load_store("waypoints"))


@app.post("/api/waypoints")
async def waypoint_upsert(request: Request):
    data = await request.json()
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "lat/lng required")
    item = {
        "id": str(data.get("id") or uuid.uuid4().hex[:10]),
        "name": str(data.get("name", "Waypoint")).strip()[:80] or "Waypoint",
        "kind": str(data.get("kind", "point"))[:20],
        "notes": str(data.get("notes", "")).strip()[:300],
        "lat": round(lat, 6), "lng": round(lng, 6),
    }
    return JSONResponse(_upsert("waypoints", item))


@app.delete("/api/waypoints/{item_id}")
def waypoint_delete(item_id: str):
    _delete("waypoints", item_id)
    return JSONResponse({"ok": True})


# ----------------------
# BIBLE (KJV)
# ----------------------
def bible_tr(request: Request, t: str = "") -> str:
    """Translation: ?t= wins, then the reader's saved choice (cookie), then the default."""
    return bible.tr_id(t or request.query_params.get("t") or request.cookies.get("bible_t"))


def _bible_ctx(request: Request, tr: str) -> dict:
    return {"tr": tr, "tr_info": bible.TRANSLATIONS[tr], "translations": bible.available()}


@app.get("/bible", response_class=HTMLResponse)
def bible_index(request: Request):
    tr = bible_tr(request)
    return render("bible/index.html", request, books=bible.books(tr), votd=bible.verse_of_the_day(tr),
                  today=bible.group_ranges(bible.plan_day(date.today().timetuple().tm_yday)), **_bible_ctx(request, tr))


@app.get("/bible/search", response_class=HTMLResponse)
def bible_search(request: Request, q: str = ""):
    tr = bible_tr(request)
    ref = bible.parse_ref(q)
    if ref:  # "John 3:16" typed into search: jump straight there
        return RedirectResponse(bible.ref_url(ref), status_code=302)
    results, total = bible.search(q, tr) if len(q.strip()) >= 2 else ([], 0)
    return render("bible/search.html", request, query=q, results=results, total=total, **_bible_ctx(request, tr))


@app.get("/bible/plan", response_class=HTMLResponse)
def bible_plan(request: Request, day: int = 0):
    day = day or date.today().timetuple().tm_yday
    day = (day - 1) % 365 + 1
    return render("bible/plan.html", request, day=day, readings=bible.group_ranges(bible.plan_day(day)),
                  chapters=bible.plan_day(day), **_bible_ctx(request, bible_tr(request)))


DEVOTIONAL_FILE = BASE_DIR / "faith" / "morning_evening.json"


@lru_cache(maxsize=1)
def _devotional() -> dict:
    try:
        return json.loads(DEVOTIONAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@app.get("/devotional", response_class=HTMLResponse)
def devotional(request: Request, d: str = ""):
    """Spurgeon's Morning and Evening for a given MM-DD (default today)."""
    from datetime import timedelta
    try:
        day = date(2024, int(d[:2]), int(d[3:5])) if re.fullmatch(r"\d{2}-\d{2}", d) else date.today().replace(year=2024)
    except ValueError:
        day = date.today().replace(year=2024)  # 2024 = leap year, so Feb 29 exists
    key = day.strftime("%m-%d")
    reading = _devotional().get(key)
    if not reading:
        return render("404.html", request, status_code=404)
    tr = bible_tr(request)
    def linked(r):
        ref = bible.parse_ref(r["ref"])
        return {**r, "url": bible.ref_url(ref) if ref else None}
    return render("faith/devotional.html", request, day=day, key=key,
                  morning=linked(reading["morning"]), evening=linked(reading["evening"]),
                  prev=(day - timedelta(days=1)).strftime("%m-%d"), next=(day + timedelta(days=1)).strftime("%m-%d"),
                  today=date.today().strftime("%m-%d"), tr=tr)


@app.get("/api/bible/urls")
def bible_urls(t: str = ""):
    q = f"?t={bible.tr_id(t)}" if t else ""
    return JSONResponse([f"/bible/{b['slug']}/{c}{q}" for b in bible.books() for c in range(1, len(b["chapters"]) + 1)])


@app.get("/bible/{book}", response_class=HTMLResponse)
def bible_book(request: Request, book: str):
    b = bible.find_book(book)
    if not b:
        return render("404.html", request, status_code=404)
    return render("bible/book.html", request, book=b, **_bible_ctx(request, bible_tr(request)))


@app.get("/bible/{book}/{chapter}", response_class=HTMLResponse)
def bible_chapter(request: Request, book: str, chapter: int, v: str = "", c: str = ""):
    tr = bible_tr(request)
    b = bible.find_book(book)
    if not b or not 1 <= chapter <= len(b["chapters"]):
        return render("404.html", request, status_code=404)
    hl = set()
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", v)
    if m:
        hl = set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    allb = bible.books()
    i = b["index"]
    if chapter > 1:
        prev = (b, chapter - 1)
    else:
        prev = (allb[i - 1], len(allb[i - 1]["chapters"])) if i > 0 else None
    if chapter < len(b["chapters"]):
        nxt = (b, chapter + 1)
    else:
        nxt = (allb[i + 1], 1) if i < len(allb) - 1 else None
    verses = list(enumerate(bible.books(tr)[i]["chapters"][chapter - 1], 1))
    compare = bible.tr_id(c) if c and bible.tr_id(c) != tr else None
    cmp_verses = dict(enumerate(bible.books(compare)[i]["chapters"][chapter - 1], 1)) if compare else {}
    trb = bible.books(tr)[i]
    headings = {int(k): v for k, v in trb.get("headings", {}).get(str(chapter), {}).items()}
    fallback = trb.get("fallback", {}).get(str(chapter))
    return render("bible/chapter.html", request, book=b, chapter=chapter, verses=verses, highlight=hl,
                  headings=headings, fallback=bible.TRANSLATIONS.get(fallback) if fallback else None,
                  prev=prev, next=nxt, compare=compare, cmp_verses=cmp_verses,
                  cmp_info=bible.TRANSLATIONS.get(compare), **_bible_ctx(request, tr))


# ----------------------
# PWA
# ----------------------
def _asset_version() -> str:
    """Changes whenever app code, templates, static files or content change."""
    newest = 0.0
    for root in (STATIC_DIR, TEMPLATE_DIR):
        for p in root.rglob("*"):
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
    newest = max([newest, Path(__file__).stat().st_mtime] + [d["mtime"] for d in index.docs()])
    return str(int(newest))


@app.get("/sw.js")
def service_worker():
    js = (STATIC_DIR / "sw.js").read_text().replace("__VERSION__", _asset_version())
    return HTMLResponse(js, media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/precache")
def precache_list():
    urls = ["/", "/offline", "/critical", "/tools", "/library", "/tags", "/map", "/install", "/bible", "/bible/plan",
            "/devotional", "/media"]
    urls += [f"/{c['name']}" for c in index.categories()]
    urls += [f"/{d['category']}/{quote(d['name'])}" for d in index.docs()]
    urls += [f"/tools/{t[0]}" for t in TOOLS]
    v = static_version()
    urls += ["/api/recipes", f"/static/style.css?v={v}", f"/static/app.js?v={v}", f"/static/geo.js?v={v}", f"/static/map.js?v={v}",
             "/static/vendor/leaflet.js", "/static/vendor/leaflet.css", "/static/vendor/protomaps-leaflet.js",
             "/static/favicon.svg", "/manifest.webmanifest", "/static/data/canning.json"]
    urls += [f"/static/{p.relative_to(STATIC_DIR).as_posix()}" for p in (STATIC_DIR / "fonts").glob("*.woff2")]
    urls += [f"/static/img/{p.name}" for p in (STATIC_DIR / "img").iterdir() if p.is_file()]
    return JSONResponse(urls)


TLS_DIR = Path(os.environ.get("ARK_TLS_DIR", "/etc/ark-tls"))


@app.get("/welcome", response_class=HTMLResponse)
def welcome_page(request: Request):
    """Landing page for the Wi-Fi captive portal: how to open and save ARK."""
    host = request.url.hostname or "localhost"
    return render("welcome.html", request, host=host, https_url=f"https://{host}/")


@app.get("/install", response_class=HTMLResponse)
def install_page(request: Request):
    secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    host = request.url.hostname or "localhost"
    return render("install.html", request, secure=secure, https_url=f"https://{host}/",
                  has_ca=(TLS_DIR / "ca.crt").is_file())


@app.get("/ark-ca.crt")
def ca_cert():
    path = TLS_DIR / "ca.crt"
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/x-x509-ca-cert", filename="ARK-Local-CA.crt")


@app.get("/offline", response_class=HTMLResponse)
def offline_page(request: Request):
    return render("offline.html", request)


# ----------------------
# IMPORT (upload your own files, e.g. a Bible translation you own)
# ----------------------
IMPORT_DIR = Path(os.environ.get("OFFLINE_IMPORT_DIR", "/opt/offline-data/imports"))
IMPORT_EXT = {".sql", ".sqlite", ".db", ".json", ".csv", ".tsv", ".txt", ".xml", ".usfm", ".zip", ".pdf", ".epub"}
IMPORT_MAX = 500 * 1024 * 1024


def _imports() -> list[dict]:
    if not IMPORT_DIR.is_dir():
        return []
    return [{"name": p.name, "size": human_size(p.stat().st_size)}
            for p in sorted(IMPORT_DIR.iterdir()) if p.is_file() and not p.name.endswith(".part")]


@app.get("/import", response_class=HTMLResponse)
def import_page(request: Request, ok: str = ""):
    return render("import.html", request, files=_imports(), ok=ok, exts=sorted(IMPORT_EXT), import_dir=str(IMPORT_DIR))


@app.post("/import")
async def import_upload(file: UploadFile = File(...)):
    name = Path(file.filename or "").name
    if not name or Path(name).suffix.lower() not in IMPORT_EXT:
        raise HTTPException(400, "File type not allowed")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMPORT_DIR / re.sub(r"[^\w.\- ]", "_", name)
    tmp = dest.with_name(dest.name + ".part")
    size = 0
    with open(tmp, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > IMPORT_MAX:
                f.close(); tmp.unlink(missing_ok=True)
                raise HTTPException(413, "File too large (max 500 MB)")
            f.write(chunk)
    tmp.replace(dest)
    return RedirectResponse(f"/import?ok={quote(dest.name)}", status_code=303)


# ----------------------
# NEW / SAVE ITEM
# ----------------------
def _valid_category(category: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_\-]+", category))


@app.get("/{category}/new", response_class=HTMLResponse)
def new_item(request: Request, category: str):
    if not _valid_category(category):
        raise HTTPException(404)
    return render("new.html", request, category=category, cat=category_info(category))


@app.post("/{category}/save")
def save_item(
    category: str,
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
):
    if not _valid_category(category):
        raise HTTPException(400, "Invalid category")
    title = title.strip()
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    if not slug:
        raise HTTPException(400, "Title required")

    path = CONTENT_DIR / category
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / f"{slug}.md"
    n = 2
    while filepath.exists():
        filepath = path / f"{slug}_{n}.md"
        n += 1

    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    front = yaml.safe_dump({"title": title, "category": category, "tags": tag_list},
                           sort_keys=False, allow_unicode=True, default_flow_style=None)
    filepath.write_text(f"---\n{front}---\n\n# {title}\n\n{content.strip()}\n", encoding="utf-8")
    return RedirectResponse(f"/{category}/{filepath.stem}", status_code=303)


# ----------------------
# CATEGORY PAGE
# ----------------------
@app.get("/{category}", response_class=HTMLResponse)
def view_category(request: Request, category: str):
    if not (CONTENT_DIR / category).is_dir() or category.startswith((".", "_")):
        return render("404.html", request, status_code=404)
    items = index.in_category(category)
    return render("category.html", request, cat=category_info(category, len(items)), items=items,
                  votd=bible.verse_of_the_day(bible_tr(request)) if category == "faith" else None)


# ----------------------
# VIEW ITEM
# ----------------------
@app.get("/{category}/{name}", response_class=HTMLResponse)
def view_item(request: Request, category: str, name: str):
    doc = index.get(category, name)
    if not doc:
        return render("404.html", request, status_code=404)

    html, toc = render_markdown(doc["body"], scripture_links=(category == "faith"), tr=bible_tr(request))
    tags = set(doc["tags"])
    ctx = dict(
        doc=doc,
        name=name,
        category=category,
        cat=category_info(category),
        metadata=doc["metadata"],
        content=html,
        toc=[t for t in (toc[0]["children"] if len(toc) == 1 else toc)],
        hazard=bool(HAZARD_TAGS & tags),
        priority=bool(PRIORITY_TAGS & tags),
        related=[d for d in index.in_category(category) if d["name"] != name][:5],
    )
    if category == "recipes":
        return render("recipe.html", request, parts=split_recipe(html), **ctx)
    return render("item.html", request, **ctx)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return render("404.html", request, status_code=404)
