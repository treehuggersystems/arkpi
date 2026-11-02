#!/usr/bin/env python3
"""Build the offline Bible translations in app/bible/*.json (all public domain).

    # King James Version — Project Gutenberg eBook #10
    curl -L -o pg10.txt https://www.gutenberg.org/cache/epub/10/pg10.txt
    python3 scripts/build-bible.py kjv pg10.txt

    # Berean Standard Bible — dedicated to the public domain (2023)
    curl -L -o bsb.txt https://bereanbible.com/bsb.txt
    python3 scripts/build-bible.py bsb bsb.txt

    # World English Bible — public domain (eBible.org, Protestant canon)
    curl -L -o engwebp_vpl.zip https://ebible.org/Scriptures/engwebp_vpl.zip && unzip engwebp_vpl.zip
    python3 scripts/build-bible.py web engwebp_vpl.txt

Output: a list of books, each {"name", "abbr", "testament", "chapters": [[verse, ...], ...]}.
"""
import json
import re
import sys
from pathlib import Path

BOOKS = [
    ("Genesis", "Gen"), ("Exodus", "Exod"), ("Leviticus", "Lev"), ("Numbers", "Num"), ("Deuteronomy", "Deut"),
    ("Joshua", "Josh"), ("Judges", "Judg"), ("Ruth", "Ruth"), ("1 Samuel", "1Sam"), ("2 Samuel", "2Sam"),
    ("1 Kings", "1Kgs"), ("2 Kings", "2Kgs"), ("1 Chronicles", "1Chr"), ("2 Chronicles", "2Chr"), ("Ezra", "Ezra"),
    ("Nehemiah", "Neh"), ("Esther", "Esth"), ("Job", "Job"), ("Psalms", "Ps"), ("Proverbs", "Prov"),
    ("Ecclesiastes", "Eccl"), ("Song of Solomon", "Song"), ("Isaiah", "Isa"), ("Jeremiah", "Jer"),
    ("Lamentations", "Lam"), ("Ezekiel", "Ezek"), ("Daniel", "Dan"), ("Hosea", "Hos"), ("Joel", "Joel"),
    ("Amos", "Amos"), ("Obadiah", "Obad"), ("Jonah", "Jonah"), ("Micah", "Mic"), ("Nahum", "Nah"),
    ("Habakkuk", "Hab"), ("Zephaniah", "Zeph"), ("Haggai", "Hag"), ("Zechariah", "Zech"), ("Malachi", "Mal"),
    ("Matthew", "Matt"), ("Mark", "Mark"), ("Luke", "Luke"), ("John", "John"), ("Acts", "Acts"),
    ("Romans", "Rom"), ("1 Corinthians", "1Cor"), ("2 Corinthians", "2Cor"), ("Galatians", "Gal"),
    ("Ephesians", "Eph"), ("Philippians", "Phil"), ("Colossians", "Col"), ("1 Thessalonians", "1Thess"),
    ("2 Thessalonians", "2Thess"), ("1 Timothy", "1Tim"), ("2 Timothy", "2Tim"), ("Titus", "Titus"),
    ("Philemon", "Phlm"), ("Hebrews", "Heb"), ("James", "Jas"), ("1 Peter", "1Pet"), ("2 Peter", "2Pet"),
    ("1 John", "1John"), ("2 John", "2John"), ("3 John", "3John"), ("Jude", "Jude"), ("Revelation", "Rev"),
]


def build_kjv(src: Path) -> list[dict]:
    text = src.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    start = text.index("*** START OF")
    end = text.index("*** END OF")
    body = text[text.index("\n", start) + 1:end]

    # Book titles (from the table of contents) and a few sub-headings are the only
    # non-verse paragraphs. Any other paragraph — or text before the first verse
    # marker in a paragraph — continues the previous verse.
    toc_end = body.index("\n1:1 ")
    headings = {re.sub(r"\s+", " ", l).strip() for l in body[:toc_end].split("\n") if l.strip()}
    headings |= {"Otherwise Called:", "Commonly Called:", "The Third Book of the Kings",
                 "The Fourth Book of the Kings", "or", "The Preacher", "***",
                 "The New Testament of the King James Bible",
                 "The Old Testament of the King James Version of the Bible"}
    verse_re = re.compile(r"(?:(?<=\s)|^)(\d+):(\d+)\s")
    books, chapters, last = [], None, None
    for para in re.split(r"\n\s*\n", body[toc_end:]):
        flat = re.sub(r"\s+", " ", para).strip()
        if not flat or flat in headings:
            continue
        marks = list(verse_re.finditer(flat))
        lead = flat[:marks[0].start()].strip() if marks else flat
        if lead:
            if last is None:
                raise SystemExit(f"unexpected text before first verse: {lead[:60]}")
            chapters_ref, c0, v0 = last
            chapters_ref[c0][v0] += " " + lead
        for k, m in enumerate(marks):
            c, v = int(m.group(1)), int(m.group(2))
            txt = flat[m.end():marks[k + 1].start() if k + 1 < len(marks) else len(flat)].strip()
            if c == 1 and v == 1:
                name, abbr = BOOKS[len(books)]
                chapters = []
                books.append({"name": name, "abbr": abbr,
                              "testament": "OT" if len(books) < 39 else "NT", "chapters": chapters})
            while len(chapters) < c:
                chapters.append([])
            if v != len(chapters[c - 1]) + 1:
                raise SystemExit(f"{books[-1]['name']} {c}:{v}: verse out of order")
            chapters[c - 1].append(txt)
            last = (chapters, c - 1, v - 1)

    return books


def _from_rows(rows) -> list[dict]:
    """rows: iterable of (book_key, chapter, verse, text) in canonical order."""
    books, keys = [], []
    for key, c, v, text in rows:
        if not keys or keys[-1] != key:
            keys.append(key)
            name, abbr = BOOKS[len(books)]
            books.append({"name": name, "abbr": abbr, "testament": "OT" if len(books) < 39 else "NT", "chapters": []})
        chapters = books[-1]["chapters"]
        while len(chapters) < c:
            chapters.append([])
        if v != len(chapters[c - 1]) + 1:
            raise SystemExit(f"{books[-1]['name']} {c}:{v}: verse out of order")
        chapters[c - 1].append(re.sub(r"\s+", " ", text).strip())
    return books


def build_bsb(src: Path) -> list[dict]:
    row = re.compile(r"^(.+?) (\d+):(\d+)\t(.*)$")
    def rows():
        for line in src.read_text(encoding="utf-8-sig").splitlines():
            m = row.match(line)
            if m:
                yield m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    return _from_rows(rows())


def build_vpl(src: Path) -> list[dict]:
    row = re.compile(r"^([1-3A-Z]{3}) (\d+):(\d+) (.*)$")
    def rows():
        for line in src.read_text(encoding="utf-8-sig").splitlines():
            m = row.match(line)
            if m:
                yield m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    return _from_rows(rows())


def main(kind: str, src: Path, out: Path):
    books = {"kjv": build_kjv, "bsb": build_bsb, "web": build_vpl}[kind](src)
    n_ch = sum(len(b["chapters"]) for b in books)
    n_v = sum(len(c) for b in books for c in b["chapters"])
    print(f"{kind}: {len(books)} books, {n_ch} chapters, {n_v} verses")
    assert len(books) == 66 and n_ch == 1189, "unexpected book/chapter count"
    if kind == "kjv":
        assert n_v == 31102
    assert abs(n_v - 31102) < 10, "verse count far from expected"
    assert re.match(r"In the beginning,? God created", books[0]["chapters"][0][0])
    assert "God so loved the world" in books[42]["chapters"][2][15]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(books, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    kind, src = sys.argv[1], Path(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).resolve().parent.parent / f"app/bible/{kind}.json"
    main(kind, src, out)
