"""Offline Bible: translations, reference parsing, search, reading plans.

Texts live in app/bible/<id>.json, built by scripts/build-bible.py. All are
public domain: KJV (Project Gutenberg #10), Berean Standard Bible (dedicated to
the public domain 2023), World English Bible (eBible.org).
"""

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

BIBLE_DIR = Path(__file__).resolve().parent / "bible"
TRANSLATIONS = {
    "esv": {"name": "English Standard Version", "short": "ESV", "note": "Personal licensed copy (git-ignored, never redistributed).",
            "copyright": "Scripture quotations are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved."},
    "bsb": {"name": "Berean Standard Bible", "short": "BSB", "note": "Modern, accurate, readable (2023). Public domain."},
    "kjv": {"name": "King James Version", "short": "KJV", "note": "The classic 1611 / 1769 text. Public domain."},
    "web": {"name": "World English Bible", "short": "WEB", "note": "Modern update of the 1901 ASV. Public domain."},
}
# Default: the first available of these (ESV when a personal copy is installed).
DEFAULT_TR = next((t for t in ("esv", "bsb", "kjv") if (BIBLE_DIR / f"{t}.json").is_file()), "kjv")

# Extra spellings people actually type, beyond full names and the stored abbreviations.
EXTRA_ALIASES = {
    "gn": "Genesis", "ex": "Exodus", "exo": "Exodus", "lv": "Leviticus", "nm": "Numbers", "dt": "Deuteronomy",
    "jos": "Joshua", "jdg": "Judges", "jg": "Judges", "ru": "Ruth", "1sa": "1 Samuel", "2sa": "2 Samuel",
    "1ki": "1 Kings", "2ki": "2 Kings", "1ch": "1 Chronicles", "2ch": "2 Chronicles", "ne": "Nehemiah",
    "es": "Esther", "jb": "Job", "psa": "Psalms", "psalm": "Psalms", "pss": "Psalms", "pr": "Proverbs",
    "pro": "Proverbs", "ec": "Ecclesiastes", "ecc": "Ecclesiastes", "qoh": "Ecclesiastes",
    "so": "Song of Solomon", "sos": "Song of Solomon", "song of songs": "Song of Solomon", "canticles": "Song of Solomon",
    "is": "Isaiah", "je": "Jeremiah", "la": "Lamentations", "eze": "Ezekiel", "ezk": "Ezekiel", "dn": "Daniel",
    "da": "Daniel", "ho": "Hosea", "jl": "Joel", "am": "Amos", "ob": "Obadiah", "jon": "Jonah", "mi": "Micah",
    "na": "Nahum", "hb": "Habakkuk", "zep": "Zephaniah", "hg": "Haggai", "zec": "Zechariah", "ml": "Malachi",
    "mt": "Matthew", "mat": "Matthew", "mk": "Mark", "mr": "Mark", "lk": "Luke", "jn": "John", "jhn": "John",
    "ac": "Acts", "ro": "Romans", "rm": "Romans", "1co": "1 Corinthians", "2co": "2 Corinthians",
    "ga": "Galatians", "ep": "Ephesians", "php": "Philippians", "pp": "Philippians", "co": "Colossians",
    "1th": "1 Thessalonians", "2th": "2 Thessalonians", "1ti": "1 Timothy", "2ti": "2 Timothy", "tit": "Titus",
    "phm": "Philemon", "philem": "Philemon", "he": "Hebrews", "jm": "James", "jam": "James", "1pe": "1 Peter",
    "2pe": "2 Peter", "1jn": "1 John", "2jn": "2 John", "3jn": "3 John", "jud": "Jude", "re": "Revelation",
    "rv": "Revelation", "revelations": "Revelation", "apocalypse": "Revelation",
}


def tr_id(t: str | None) -> str:
    t = (t or "").lower()
    return t if t in TRANSLATIONS and (BIBLE_DIR / f"{t}.json").is_file() else DEFAULT_TR


def available() -> list[dict]:
    return [{"id": k, **v} for k, v in TRANSLATIONS.items() if (BIBLE_DIR / f"{k}.json").is_file()]


@lru_cache(maxsize=4)
def books(tr: str = "kjv") -> list[dict]:
    data = json.loads((BIBLE_DIR / f"{tr_id(tr)}.json").read_text(encoding="utf-8"))
    for i, b in enumerate(data):
        b["index"] = i
        b["slug"] = slug(b["name"])
    return data


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


@lru_cache(maxsize=1)
def _aliases() -> dict[str, dict]:
    out = {}
    for b in books():
        name = b["name"]
        keys = {name, b["abbr"], b["slug"]}
        # "1 John" -> "1john", "i john", "first john"
        m = re.match(r"([123]) (.+)", name)
        if m:
            n, rest = m.groups()
            roman = {"1": "i", "2": "ii", "3": "iii"}[n]
            word = {"1": "first", "2": "second", "3": "third"}[n]
            keys |= {f"{n}{rest}", f"{roman} {rest}", f"{word} {rest}"}
        for k in keys:
            out[_norm(k)] = b
    for k, v in EXTRA_ALIASES.items():
        out[_norm(k)] = next(b for b in books() if b["name"] == v)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s.]+", "", s.lower())


def find_book(name: str):
    return _aliases().get(_norm(name)) or next(
        (b for k, b in _aliases().items() if len(_norm(name)) >= 3 and k.startswith(_norm(name))), None)


REF_RE = re.compile(
    r"^\s*((?:[123]|i{1,3}|first|second|third)?\s*[A-Za-z][A-Za-z .]*?)\.?\s*"
    r"(\d+)(?:\s*:\s*(\d+)(?:\s*[-–]\s*(\d+))?)?\s*$", re.I)


def parse_ref(text: str):
    """'John 3:16', 'Ps 23', 'Rom 8:28-39', '1 Cor 13' -> dict or None."""
    m = REF_RE.match(text or "")
    if not m:
        return None
    book = find_book(m.group(1))
    if not book:
        return None
    ch = int(m.group(2))
    if not 1 <= ch <= len(book["chapters"]):
        return None
    n = len(book["chapters"][ch - 1])
    v1 = int(m.group(3)) if m.group(3) else None
    v2 = int(m.group(4)) if m.group(4) else v1
    if v1 is not None and not (1 <= v1 <= n):
        return None
    if v2 is not None:
        v2 = min(max(v2, v1), n)
    return {"book": book, "chapter": ch, "v1": v1, "v2": v2}


def ref_label(ref: dict) -> str:
    name = ref["book"]["name"]
    if name == "Psalms":
        name = "Psalm"
    s = f"{name} {ref['chapter']}"
    if ref["v1"]:
        s += f":{ref['v1']}" + (f"–{ref['v2']}" if ref["v2"] and ref["v2"] != ref["v1"] else "")
    return s


def ref_url(ref: dict) -> str:
    url = f"/bible/{ref['book']['slug']}/{ref['chapter']}"
    if ref["v1"]:
        url += f"?v={ref['v1']}" + (f"-{ref['v2']}" if ref["v2"] != ref["v1"] else "") + f"#v{ref['v1']}"
    return url


def ref_verses(ref: dict, tr: str = "kjv") -> list[tuple[int, str]]:
    ch = books(tr)[ref["book"]["index"]]["chapters"][ref["chapter"] - 1]
    if not ref["v1"]:
        return list(enumerate(ch, 1))
    return [(i, ch[i - 1]) for i in range(ref["v1"], min(ref["v2"], len(ch)) + 1)]


def search(query: str, tr: str = "kjv", limit: int = 300):
    """Case-insensitive search; all words must appear in the verse. Quotes = exact phrase."""
    q = query.strip()
    phrase = None
    m = re.fullmatch(r'"(.+)"', q)
    if m:
        phrase = m.group(1).lower()
    words = [w for w in re.findall(r"[\w']+", q.lower())]
    results, total = [], 0
    for b in books(tr):
        for c, chapter in enumerate(b["chapters"], 1):
            for v, text in enumerate(chapter, 1):
                low = text.lower()
                ok = (phrase in low) if phrase else all(re.search(rf"\b{re.escape(w)}", low) for w in words)
                if ok:
                    total += 1
                    if len(results) < limit:
                        results.append({"book": b, "chapter": c, "verse": v, "text": text})
    return results, total


# ---- Reading plan: whole Bible in a year, OT and NT in parallel ---------------

def _split(chapters: list[tuple[int, int]], days: int) -> list[list[tuple[int, int]]]:
    out, n = [], len(chapters)
    for d in range(days):
        a, z = round(d * n / days), round((d + 1) * n / days)
        out.append(chapters[a:z])
    return out


@lru_cache(maxsize=1)
def year_plan() -> list[list[tuple[int, int]]]:
    ot = [(b["index"], c) for b in books() if b["testament"] == "OT" for c in range(1, len(b["chapters"]) + 1)]
    nt = [(b["index"], c) for b in books() if b["testament"] == "NT" for c in range(1, len(b["chapters"]) + 1)]
    return [o + n for o, n in zip(_split(ot, 365), _split(nt, 365))]


def plan_day(day: int) -> list[dict]:
    day = (day - 1) % 365
    return [{"book": books()[bi], "chapter": c} for bi, c in year_plan()[day]]


def group_ranges(readings: list[dict]) -> list[dict]:
    """[(Gen,1),(Gen,2),(Gen,3)] -> 'Genesis 1–3'."""
    groups = []
    for r in readings:
        if groups and groups[-1]["book"] is r["book"] and groups[-1]["end"] == r["chapter"] - 1:
            groups[-1]["end"] = r["chapter"]
        else:
            groups.append({"book": r["book"], "start": r["chapter"], "end": r["chapter"]})
    for g in groups:
        name = g["book"]["name"]
        g["label"] = f"{name} {g['start']}" + (f"–{g['end']}" if g["end"] != g["start"] else "")
        g["url"] = f"/bible/{g['book']['slug']}/{g['start']}"
    return groups


# ---- Verse of the day ----------------------------------------------------------

DAILY = [
    "Joshua 1:9", "Psalm 46:1", "Isaiah 41:10", "Philippians 4:6-7", "Proverbs 3:5-6", "Romans 8:28",
    "Psalm 23:4", "Matthew 6:33-34", "Isaiah 40:31", "John 16:33", "2 Timothy 1:7", "Psalm 121:1-2",
    "Lamentations 3:22-23", "Hebrews 13:5-6", "Psalm 27:1", "Romans 8:38-39", "Deuteronomy 31:6",
    "Psalm 91:1-2", "Matthew 11:28-30", "1 Peter 5:7", "Psalm 34:18", "Isaiah 26:3", "John 14:27",
    "Nahum 1:7", "Psalm 56:3-4", "2 Corinthians 4:16-18", "Psalm 62:5-6", "Romans 15:13", "Hebrews 11:7",
    "Philippians 4:19", "Psalm 37:25", "Proverbs 18:10", "James 1:2-4", "Psalm 18:2", "Micah 7:7",
    "Habakkuk 3:17-18", "2 Chronicles 7:14", "Psalm 31:24", "John 11:25-26", "Revelation 21:4",
    "Psalm 4:8", "Isaiah 43:2", "Romans 5:8", "Psalm 32:7", "1 Corinthians 10:13", "Psalm 55:22",
    "Zephaniah 3:17", "Ephesians 6:10-11", "Psalm 118:6", "Matthew 28:20",
]


def verse_of_the_day(tr: str = DEFAULT_TR, d: date | None = None) -> dict:
    d = d or date.today()
    ref = parse_ref(DAILY[d.toordinal() % len(DAILY)])
    return {"label": ref_label(ref), "url": ref_url(ref), "short": TRANSLATIONS[tr_id(tr)]["short"],
            "text": " ".join(t for _, t in ref_verses(ref, tr))}


# ---- Markdown helpers: [[John 3:16]] embeds, auto-linked references ---------------

EMBED_RE = re.compile(r"^\[\[([^\]]+)\]\]\s*$", re.M)


def expand_embeds(body: str, tr: str = DEFAULT_TR) -> str:
    """Replace a line '[[Psalm 23]]' with the verses as a scripture blockquote."""
    short = TRANSLATIONS[tr_id(tr)]["short"]

    def repl(m):
        ref = parse_ref(m.group(1))
        if not ref:
            return m.group(0)
        verses = ref_verses(ref, tr)
        lines = [f'<sup class="vn">{n}</sup>{_esc(t)}' if len(verses) > 1 else _esc(t) for n, t in verses]
        text = " ".join(lines)
        return (f'<blockquote class="scripture"><p>{text}</p>'
                f'<cite><a href="{ref_url(ref)}">{ref_label(ref)}</a> · {short}</cite></blockquote>')
    return EMBED_RE.sub(repl, body)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ref_pattern() -> re.Pattern:
    names = sorted({b["name"] for b in books()} | {"Psalm"}, key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w/\[])((?:{alt})\.? \d+(?::\d+(?:[-–]\d+)?)?)(?![\w\]])")


@lru_cache(maxsize=1)
def _cached_ref_pattern():
    return _ref_pattern()


def link_refs_html(html: str) -> str:
    """Turn plain-text references like 'Romans 8:28' in rendered HTML into reader links
    (skipping text already inside links)."""
    pat = _cached_ref_pattern()
    parts = re.split(r"(<a\b.*?</a>|<[^>]+>)", html, flags=re.S)
    for i, part in enumerate(parts):
        if part.startswith("<"):
            continue
        def repl(m):
            ref = parse_ref(m.group(1))
            return f'<a class="ref" href="{ref_url(ref)}">{m.group(1)}</a>' if ref else m.group(1)
        parts[i] = pat.sub(repl, part)
    return "".join(parts)
