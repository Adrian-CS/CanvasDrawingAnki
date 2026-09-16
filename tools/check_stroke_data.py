#!/usr/bin/env python3
"""Sanity-check the committed stroke dataset.

Regenerating the data needs the KanjiVG release archive, which is too big
to pull on every build, so this validates the file that is actually
shipped: that it decodes, that its format is intact, and that a sample of
characters still has the stroke count it is supposed to have. A corrupt
or truncated data file would otherwise only show up as mysteriously wrong
verdicts during review.

Usage:  python tools/check_stroke_data.py
"""

from __future__ import annotations

import gzip
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "drawing", "data", "strokes.js.gz")
ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")

# Stroke counts checked against the standard counts for these characters,
# spanning the range from a single stroke to one of the densest kanji.
SPOT_CHECKS = {
    "一": 1, "二": 2, "日": 4, "永": 5, "国": 8, "書": 10,
    "漢": 13, "愛": 13, "語": 14, "鬱": 29, "あ": 3, "ア": 2,
}
MIN_CHARACTERS = 6000


def fail(msg: str) -> None:
    print("FAIL: " + msg)
    sys.exit(1)


def main() -> int:
    if not os.path.exists(DATA):
        fail(f"{DATA} is missing — run tools/build_stroke_data.py")

    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        js = fh.read()

    marker = 'window.KDA_STROKE_DATA="'
    if marker not in js:
        fail("the data file does not assign window.KDA_STROKE_DATA")
    body = js.split(marker, 1)[1].rsplit('";', 1)[0].replace("\\n", "\n")

    if not body.startswith("\n") or not body.endswith("\n"):
        fail("the payload must be newline-delimited at both ends — lookups "
             "search for '\\n' + character + '|'")

    entries = {}
    for line in body.strip("\n").split("\n"):
        char, _, strokes = line.partition("|")
        if not char or not strokes:
            fail(f"malformed line: {line[:40]!r}")
        if char in entries:
            fail(f"duplicate entry for {char}")
        parsed = []
        for stroke in strokes.split(","):
            if len(stroke) < 4 or len(stroke) % 2:
                fail(f"{char}: stroke of invalid length {len(stroke)}")
            if set(stroke) - ALPHABET:
                fail(f"{char}: stroke contains characters outside the alphabet")
            parsed.append(stroke)
        entries[char] = parsed

    if len(entries) < MIN_CHARACTERS:
        fail(f"only {len(entries)} characters — expected at least {MIN_CHARACTERS}")

    for char, expected in SPOT_CHECKS.items():
        if char not in entries:
            fail(f"{char} is missing from the dataset")
        got = len(entries[char])
        if got != expected:
            fail(f"{char} has {got} strokes, expected {expected}")

    total = sum(len(v) for v in entries.values())
    print(f"ok — {len(entries)} characters, {total} strokes, "
          f"{len(body.encode('utf-8')) / 1024:.0f} KiB expanded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
