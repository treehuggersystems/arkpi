#!/usr/bin/env python3
"""Generate the procedural topographic-contour artwork used across the UI.

    python3 scripts/gen-topo.py            -> app/static/img/topo.svg

Pure standard library: fractal value noise + marching squares. The SVG is
single-colour (black strokes) so CSS can use it as a mask and tint it with
the active theme's accent colour.
"""
import math
import random
import sys
from pathlib import Path

W, H = 1600, 900          # output size (px)
STEP = 10                 # grid resolution (px)
LEVELS = 22               # number of contour levels
SEED = 1776

random.seed(SEED)
GX, GY = W // STEP + 1, H // STEP + 1


def make_noise(cells):
    grid = [[random.random() for _ in range(cells + 2)] for _ in range(cells + 2)]

    def smooth(t):
        return t * t * (3 - 2 * t)

    def sample(x, y):
        x0, y0 = int(x), int(y)
        fx, fy = smooth(x - x0), smooth(y - y0)
        a, b = grid[y0][x0], grid[y0][x0 + 1]
        c, d = grid[y0 + 1][x0], grid[y0 + 1][x0 + 1]
        return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy
    return sample


octaves = [(make_noise(8), 4.0, 1.0), (make_noise(16), 8.0, 0.5), (make_noise(32), 16.0, 0.25), (make_noise(64), 32.0, 0.12)]


def height(px, py):
    u, v = px / W, py / H
    h = sum(amp * fn(u * freq + 0.5, v * freq * H / W + 0.5) for fn, freq, amp in octaves)
    # A couple of ridges so it reads like real terrain rather than blobs.
    h += 0.55 * math.exp(-((u - 0.72) ** 2 / 0.03 + (v - 0.35) ** 2 / 0.05))
    h += 0.35 * math.exp(-((u - 0.22) ** 2 / 0.02 + (v - 0.7) ** 2 / 0.04))
    return h


field = [[height(x * STEP, y * STEP) for x in range(GX)] for y in range(GY)]
lo = min(map(min, field))
hi = max(map(max, field))


def interp(p1, p2, v1, v2, level):
    t = (level - v1) / (v2 - v1) if v2 != v1 else 0.5
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def contour_segments(level):
    segs = []
    for y in range(GY - 1):
        for x in range(GX - 1):
            tl, tr = field[y][x], field[y][x + 1]
            bl, br = field[y + 1][x], field[y + 1][x + 1]
            idx = (tl > level) << 3 | (tr > level) << 2 | (br > level) << 1 | (bl > level)
            if idx in (0, 15):
                continue
            P = {
                "t": interp((x, y), (x + 1, y), tl, tr, level),
                "r": interp((x + 1, y), (x + 1, y + 1), tr, br, level),
                "b": interp((x, y + 1), (x + 1, y + 1), bl, br, level),
                "l": interp((x, y), (x, y + 1), tl, bl, level),
            }
            table = {
                1: ["lb"], 2: ["br"], 3: ["lr"], 4: ["tr"], 5: ["tl", "br"], 6: ["tb"], 7: ["tl"],
                8: ["tl"], 9: ["tb"], 10: ["tr", "lb"], 11: ["tr"], 12: ["lr"], 13: ["br"], 14: ["lb"],
            }
            for e in table[idx]:
                segs.append((P[e[0]], P[e[1]]))
    return segs


def chain(segs):
    """Join segments into polylines so the SVG stays small."""
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    ends = {}
    for i, (a, b) in enumerate(segs):
        ends.setdefault(key(a), []).append(i)
        ends.setdefault(key(b), []).append(i)
    used = [False] * len(segs)
    lines = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        line = [segs[i][0], segs[i][1]]
        for forward in (True, False):
            while True:
                tip = line[-1] if forward else line[0]
                nxt = next((j for j in ends.get(key(tip), []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = segs[nxt]
                other = b if key(a) == key(tip) else a
                line.append(other) if forward else line.insert(0, other)
        lines.append(line)
    return lines


paths = []
for n in range(1, LEVELS):
    level = lo + (hi - lo) * n / LEVELS
    major = n % 5 == 0
    for line in chain(contour_segments(level)):
        if len(line) < 4:
            continue
        d = "M" + " L".join(f"{p[0] * STEP:.0f},{p[1] * STEP:.0f}" for p in line[::2] + [line[-1]])
        paths.append(f'<path d="{d}" stroke-width="{1.6 if major else 0.8}"/>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
       f'<g fill="none" stroke="#000" stroke-linejoin="round">{"".join(paths)}</g></svg>\n')
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "app/static/img/topo.svg"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(svg)
print(f"wrote {out} ({len(svg) / 1024:.0f} KB, {len(paths)} paths)")
