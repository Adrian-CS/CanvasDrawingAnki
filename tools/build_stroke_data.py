#!/usr/bin/env python3
"""Generate the compact stroke-reference dataset from KanjiVG.

Usage:
    python tools/build_stroke_data.py /path/to/kanjivg/kanji

Reads KanjiVG's per-character SVGs and writes
``drawing/data/strokes.js.gz`` — a gzipped JavaScript file that the add-on
expands into the collection media folder as ``_kda_strokes.js``.

Output format (one line per character, see drawing/data/README.md):

    <char>|<stroke>,<stroke>,…

Each stroke is a polyline; each point is two base64 characters (x then y),
each quantised to 0-63 over KanjiVG's 109x109 em box. Points are the
Ramer-Douglas-Peucker simplification of the flattened Bézier path, so
straight strokes cost 4 bytes and only genuinely curved or bent ones pay
for extra points. The runtime resamples these polylines to a fixed point
count when it compares them against what the user drew.

KanjiVG is (C) Ulrich Apel, CC BY-SA 3.0 — https://kanjivg.tagaini.net
"""

from __future__ import annotations

import gzip
import os
import re
import sys

# KanjiVG em box. Every coordinate in the source SVGs lives in 0..109.
EM = 109.0
# Quantisation levels per axis: 64 keeps a point at two base64 chars while
# staying under 2 em units (~1.7% of the glyph) of positional error, an
# order of magnitude finer than the matching tolerances.
LEVELS = 64
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
# Flattening resolution for each cubic segment, and the RDP epsilon (in em
# units) used to throw the redundant points back out afterwards.
BEZIER_STEPS = 24
RDP_EPSILON = 1.2
MAX_POINTS = 16

_PATH_D_RE = re.compile(r'<path[^>]*\sd="([^"]+)"')
_FILENAME_RE = re.compile(r"^([0-9a-f]{5})\.svg$")
_TOKEN_RE = re.compile(r"[MmCcSs]|-?\d*\.?\d+(?:e-?\d+)?")


# ── SVG path flattening ───────────────────────────────────────────────


def _cubic(p0, p1, p2, p3, steps):
    """Sample a cubic Bézier, excluding its start point."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1.0 - t
        a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        out.append(
            (
                a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
            )
        )
    return out


def flatten_path(d: str) -> list[tuple[float, float]]:
    """Turn one KanjiVG path into a dense polyline.

    KanjiVG only ever uses M/m, C/c and S/s, so this deliberately handles
    just those — anything else means the source data changed shape and is
    better off raising than being silently mis-drawn.
    """
    tokens = _TOKEN_RE.findall(d)
    pts: list[tuple[float, float]] = []
    i = 0
    cmd = ""
    cur = (0.0, 0.0)
    # Reflection of the previous cubic's second control point, for S/s.
    prev_ctrl = None

    def num():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
        elif cmd in ("M", "m"):
            # A repeated coordinate pair after M implicitly means lineto.
            cmd = "L" if cmd == "M" else "l"
            continue
        if cmd in ("M", "m"):
            x, y = num(), num()
            cur = (x, y) if cmd == "M" else (cur[0] + x, cur[1] + y)
            pts.append(cur)
            prev_ctrl = None
            cmd = "L" if cmd == "M" else "l"
        elif cmd in ("L", "l"):
            x, y = num(), num()
            cur = (x, y) if cmd == "L" else (cur[0] + x, cur[1] + y)
            pts.append(cur)
            prev_ctrl = None
        elif cmd in ("C", "c", "S", "s"):
            rel = cmd in ("c", "s")
            if cmd in ("C", "c"):
                x1, y1 = num(), num()
                c1 = (cur[0] + x1, cur[1] + y1) if rel else (x1, y1)
            else:
                c1 = (
                    (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
                    if prev_ctrl
                    else cur
                )
            x2, y2 = num(), num()
            c2 = (cur[0] + x2, cur[1] + y2) if rel else (x2, y2)
            x, y = num(), num()
            end = (cur[0] + x, cur[1] + y) if rel else (x, y)
            if not pts:
                pts.append(cur)
            pts.extend(_cubic(cur, c1, c2, end, BEZIER_STEPS))
            cur, prev_ctrl = end, c2
        else:
            raise ValueError(f"unsupported path command {cmd!r} in {d!r}")
    return pts


# ── Simplification and encoding ───────────────────────────────────────


def _rdp(pts, eps):
    """Ramer-Douglas-Peucker: keep corners, drop collinear filler."""
    if len(pts) < 3:
        return list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = (dx * dx + dy * dy) ** 0.5
    worst, worst_i = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if norm == 0:
            dist = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
        else:
            dist = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / norm
        if dist > worst:
            worst, worst_i = dist, i
    if worst <= eps:
        return [pts[0], pts[-1]]
    return _rdp(pts[: worst_i + 1], eps)[:-1] + _rdp(pts[worst_i:], eps)


def simplify(pts, eps=RDP_EPSILON):
    """Simplify, then force the result under MAX_POINTS by relaxing eps."""
    out = _rdp(pts, eps)
    while len(out) > MAX_POINTS:
        eps *= 1.5
        out = _rdp(pts, eps)
    return out


def encode_stroke(pts) -> str:
    chars = []
    last = None
    for x, y in pts:
        qx = min(LEVELS - 1, max(0, round(x / EM * (LEVELS - 1))))
        qy = min(LEVELS - 1, max(0, round(y / EM * (LEVELS - 1))))
        # Quantisation can collapse neighbours onto the same cell; a
        # repeated point carries no information for the matcher.
        if (qx, qy) == last:
            continue
        last = (qx, qy)
        chars.append(ALPHABET[qx] + ALPHABET[qy])
    if len(chars) < 2:
        # Degenerate after quantisation (a dot-sized stroke): duplicate the
        # point so every stroke still decodes to a usable 2-point polyline.
        chars = (chars or [ALPHABET[0] * 2]) * 2
    return "".join(chars)


# ── Driver ────────────────────────────────────────────────────────────


def build(src_dir: str) -> str:
    lines = []
    for name in sorted(os.listdir(src_dir)):
        m = _FILENAME_RE.match(name)
        if not m:
            # Variant files (…-Kaisho.svg etc.) describe alternate
            # handwriting styles of a character that already has a base
            # entry; including them would need a UI to choose between them.
            continue
        codepoint = int(m.group(1), 16)
        char = chr(codepoint)
        with open(os.path.join(src_dir, name), encoding="utf-8") as fh:
            svg = fh.read()
        strokes = [encode_stroke(simplify(flatten_path(d)))
                   for d in _PATH_D_RE.findall(svg)]
        if not strokes:
            continue
        lines.append(char + "|" + ",".join(strokes))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = argv[1]
    body = build(src)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(here, "drawing", "data")
    os.makedirs(out_dir, exist_ok=True)
    js = (
        "/* Stroke reference data derived from KanjiVG "
        "(C) Ulrich Apel, CC BY-SA 3.0 — https://kanjivg.tagaini.net\n"
        "   Generated by tools/build_stroke_data.py — do not edit by hand. */\n"
        "window.KDA_STROKE_DATA=\"\\n" + body.replace("\n", "\\n") + "\\n\";\n"
    )
    out = os.path.join(out_dir, "strokes.js.gz")
    with gzip.open(out, "wb", compresslevel=9) as fh:
        fh.write(js.encode("utf-8"))
    print(
        f"{len(body.splitlines())} characters — "
        f"{len(js.encode('utf-8')) / 1024:.0f} KiB expanded, "
        f"{os.path.getsize(out) / 1024:.0f} KiB gzipped → {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
