#!/usr/bin/env python3
"""Build app/faith/morning_evening.json from C. H. Spurgeon's "Morning and Evening"
(public domain; plain text from the Christian Classics Ethereal Library).

    curl -L -o morneve.txt https://ccel.org/ccel/s/spurgeon/morneve/cache/morneve.txt
    python3 scripts/build-devotional.py morneve.txt
"""
import json
import re
import sys
from pathlib import Path

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def main(src: Path, out: Path):
    text = src.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    head = re.compile(rf"^(Morning|Evening), ({'|'.join(MONTHS)}) (\d+)\s*$", re.M)
    marks = list(head.finditer(text))
    readings = {}
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        body = text[m.end():end].split("_____")[0]
        body = re.sub(r"\[\d+\]", "", body)                       # link/footnote markers
        lines = [l.strip() for l in body.split("\n")]
        lines = [l for l in lines if not re.match(r"Go To (Morning|Evening) Reading", l)]
        paras, cur = [], []
        for l in lines:
            if l:
                cur.append(l)
            elif cur:
                paras.append(" ".join(cur)); cur = []
        if cur:
            paras.append(" ".join(cur))
        if len(paras) < 3:
            continue
        verse, ref, rest = paras[0], paras[1], paras[2:]
        key = f"{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(3)):02d}"
        readings.setdefault(key, {})[m.group(1).lower()] = {"verse": verse.strip(), "ref": ref.strip(), "text": rest}
    full = sum(1 for v in readings.values() if "morning" in v and "evening" in v)
    print(f"{len(readings)} days, {full} with both readings")
    assert len(readings) >= 365 and full >= 365, "parse looks incomplete"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(readings, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "morneve.txt")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "app/faith/morning_evening.json"
    main(src, out)
