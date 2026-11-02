#!/usr/bin/env python3
"""Import a personally licensed Bible translation from a MySQL dump into app/bible/<id>.json.

    python3 scripts/import-bible-sql.py /opt/offline-data/imports/BibleTexts.sql esv

Expects a table of (id, reference, text) rows where `text` is JSON in the
"blocks_v1" format ({"blocks": [{"type": "heading"|"verse"|"verse_continuation", ...}]}),
one row per chapter (rows for single verses like "John 3:16" are ignored).
The output is git-ignored: personal translations never go into the repo.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import bible  # noqa: E402  (book names, reference parsing)

TUPLE = re.compile(r"\((\d+),\s*'((?:[^'\\]|\\.)*)',\s*'((?:[^'\\]|\\.)*)'\)", re.S)


FOOTNOTE = re.compile(r"\(\d+\)")  # footnote markers like "world,(9)" — the notes themselves aren't in the dump


def clean(s: str) -> str:
    return re.sub(r"\s{2,}", " ", FOOTNOTE.sub("", s)).strip()


def unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "r": "\r", "t": "\t", "0": "\0"}.get(m.group(1), m.group(1)), s)


def main(src: Path, tr: str):
    raw = src.read_text(encoding="utf-8")
    structure = bible.books("kjv")
    out = [{"name": b["name"], "abbr": b["abbr"], "testament": b["testament"],
            "chapters": [[] for _ in b["chapters"]], "headings": {}} for b in structure]
    seen = set()
    for _, ref_s, text in TUPLE.findall(raw):
        ref_s, data = unescape(ref_s), json.loads(unescape(text))
        ref = bible.parse_ref(ref_s)
        if not ref or ref["v1"] is not None:   # skip single-verse rows
            continue
        bi, ch = ref["book"]["index"], ref["chapter"]
        verses: dict[int, str] = {}
        heads: dict[int, str] = {}
        pending, last = None, None
        for blk in data.get("blocks", []):
            t = blk.get("type")
            if t == "heading":
                txt = blk.get("text", "").strip()
                if txt and txt != ref_s and not re.fullmatch(rf"{re.escape(ref['book']['name'])} \d+", txt):
                    pending = f"{pending} · {txt}" if pending else txt
            elif t == "verse":
                v = int(blk["verse"])
                verses[v] = clean(blk.get("text", ""))
                if pending:
                    heads[v], pending = pending, None
                last = v
            elif t == "verse_continuation" and last is not None:
                verses[last] = (verses[last] + " " + clean(blk.get("text", ""))).strip()
        if not verses:
            continue
        n = max(verses)
        # Verses the translation omits (e.g. Matt 17:21 in the ESV) are kept as empty strings so numbering stays right.
        out[bi]["chapters"][ch - 1] = [verses.get(v, "") for v in range(1, n + 1)]
        if heads:
            out[bi]["headings"][str(ch)] = {str(k): v for k, v in heads.items()}
        seen.add((bi, ch))

    # Fill chapters the source doesn't fully cover (e.g. one-chapter books fetched as "Jude 1", which
    # means only verse 1) from the BSB, and record it so the reader can say so.
    fill = bible.books("bsb")
    for bi, b in enumerate(out):
        b["fallback"] = {}
        for c, ch in enumerate(b["chapters"]):
            full = len(structure[bi]["chapters"][c])
            if (bi, c + 1) in seen and len(ch) < full - 3:
                b["chapters"][c] = list(fill[bi]["chapters"][c])
                b["fallback"][str(c + 1)] = "bsb"
                print(f"  {b['name']} {c + 1}: source has {len(ch)} of {full} verses, filled from BSB")
    missing = [f"{b['name']} {c + 1}" for bi, b in enumerate(out) for c, ch in enumerate(b["chapters"]) if not ch]
    n_v = sum(1 for b in out for c in b["chapters"] for v in c if v)
    n_h = sum(len(h) for b in out for h in b["headings"].values())
    print(f"{tr}: {len(seen)} chapters, {n_v} verses, {n_h} section headings, {len(missing)} missing chapters")
    if missing:
        print("missing:", ", ".join(missing[:20]), "…" if len(missing) > 20 else "")
    assert len(seen) == 1189, "incomplete translation"
    dest = Path(__file__).resolve().parent.parent / "app" / "bible" / f"{tr}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "esv")
