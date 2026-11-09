#!/usr/bin/env python3
"""Tests for the add-on's Python side — the part that edits a collection.

Run with:  python3 tests/test_template.py

The canvas itself is tested in tests/test_checking.js. What is tested here
is everything that reaches into someone's note types: the block that gets
written into a card template, finding it again, taking it back out, and
putting the stroke data into the media folder. A regression in the
JavaScript shows up as a bad verdict on one card; a regression here edits
the templates of every note of that type, so it is worth pinning down.

Nothing here imports aqt: the collection is stood in for by the smallest
object the code actually uses.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drawing import media  # noqa: E402
from drawing import template as T  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   " + name)
    else:
        FAILURES.append(name)
        print("  FAIL " + name + (("\n         " + str(detail)) if detail else ""))


class FakeMedia:
    def __init__(self, path):
        self._dir = path

    def dir(self):
        return self._dir


class FakeModels:
    def __init__(self, models):
        self._models = models

    def all(self):
        return self._models


class FakeCol:
    """Only the two attributes drawing/media.py actually reaches for."""

    def __init__(self, media_dir, models=()):
        self.media = FakeMedia(media_dir)
        self.models = FakeModels(list(models))


# ── The block that goes into a template ───────────────────────────────

print("the injected block")

CFG = {
    "canvas_size": 280,
    "grid_type": "mi",
    "check_strokes": True,
    "check_mode": "guided",
    "canvas_characters": "kanji",
    "hint_after_misses": 2,
    "accept_after_misses": 4,
}

block = T.build_block(CFG, "Kanji")
check("the settings reach the card", all(
    bit in block for bit in ['data-size="280"', 'data-grid="mi"',
                             'data-check="1"', 'data-check-mode="guided"',
                             'data-chars="kanji"', 'data-hint-after="2"',
                             'data-accept-after="4"']),
      block[:400])
check("the chosen field is referenced, not its value",
      "{{text:Kanji}}" in block and 'id="kda-expected"' in block)
check("an unknown mode falls back rather than reaching the card",
      'data-check-mode="live"' in T.build_block({"check_mode": "nonsense"}, "F"))
check("an unknown character rule falls back too",
      'data-chars="auto"' in T.build_block({"canvas_characters": "nope"}, "F"))
check("with no field chosen there is nothing to check against",
      'id="kda-expected"' not in T.build_block(CFG))

# ── Putting it in and taking it out again ─────────────────────────────

print("\nediting a template")

ORIGINAL = "{{Kanji}}\n<div class='x'>{{Reading}}</div>\n"
injected = T.inject(ORIGINAL, CFG, "Kanji")

check("the original template is left intact above the block",
      injected.startswith(ORIGINAL))
check("the canvas is found afterwards", T.has_canvas(injected))
check("and is not found in a template without one", not T.has_canvas(ORIGINAL))
check("the field it checks against is recoverable",
      T.expected_field(injected) == "Kanji", T.expected_field(injected))
check("removing it restores the template byte for byte",
      T.remove(injected) == ORIGINAL,
      repr(T.remove(injected)[-60:]) + " vs " + repr(ORIGINAL[-60:]))
check("injecting twice does not stack two canvases",
      T.inject(injected, CFG, "Kanji") == injected)
check("removing from a template without one changes nothing",
      T.remove(ORIGINAL) == ORIGINAL)
check("a template with no field reports none",
      T.expected_field(T.inject(ORIGINAL, CFG)) == "")

# Field names are the one piece of user text that reaches the block, so
# they have to survive the round trip whatever they contain.
print("\nfield names")
for name in ["Kanji", "Character & Reading", "字 (front)", "a'b", "Front<>"]:
    one = T.inject("x", CFG, name)
    check("round trip: " + name, T.expected_field(one) == name,
          "got " + repr(T.expected_field(one)))
    check("referenced correctly: " + name, "{{text:%s}}" % name in one)

# The markers are what makes removal possible; a template holding text that
# merely looks like them must not confuse it.
print("\nthe markers")
tricky = "before " + T.MARKER_START + "not ours" + T.MARKER_END + " after\n"
check("a block already present is left alone by inject",
      T.inject(tricky, CFG, "Kanji") == tricky)
check("exactly one block is written", injected.count(T.MARKER_START) == 1
      and injected.count(T.MARKER_END) == 1)

# ── Refreshing a canvas that is already in place ──────────────────────

print("\nupdating canvases in place")

OLD = {"canvas_size": 300, "check_mode": "live", "check_strokes": True}
NEW = {"canvas_size": 250, "check_mode": "guided", "check_strokes": True,
       "hint_after_misses": 2}

placed = T.inject(ORIGINAL, OLD, "Kanji")
updated = T.refresh(placed, NEW)

check("the new settings reach the card",
      'data-size="250"' in updated and 'data-check-mode="guided"' in updated
      and 'data-hint-after="2"' in updated)
check("the old ones are gone",
      'data-size="300"' not in updated and 'data-check-mode="live"' not in updated)
check("the template around the block is untouched",
      updated.startswith(ORIGINAL))
check("exactly one block remains", updated.count(T.MARKER_START) == 1)

# The common call must not quietly unwire what the card is about.
check("the field is kept by default", T.expected_field(updated) == "Kanji")
check("a named field replaces it",
      T.expected_field(T.refresh(placed, NEW, "Reading")) == "Reading")
check("an empty name unwires it deliberately",
      T.expected_field(T.refresh(placed, NEW, "")) == "")
check("a template with no canvas is left exactly as it was",
      T.refresh(ORIGINAL, NEW) == ORIGINAL)
check("refreshing twice is the same as refreshing once",
      T.refresh(updated, NEW) == updated)

# Both sides, since a back template that does not embed the front side gets
# its own canvas and would otherwise be left on the old settings.
model = {"tmpls": [
    {"name": "Card 1", "qfmt": T.inject("q", OLD, "Kanji"),
     "afmt": T.inject("a", OLD, "Kanji")},
    {"name": "Card 2", "qfmt": T.inject("q2", OLD, "Word"), "afmt": "plain"},
    {"name": "Card 3", "qfmt": "no canvas", "afmt": "none either"},
]}
count = T.refresh_model(model, NEW)
check("every canvas in the note type is counted", count == 3, count)
check("the back side is updated too",
      'data-size="250"' in model["tmpls"][0]["afmt"])
check("each template keeps its own field",
      T.expected_field(model["tmpls"][0]["qfmt"]) == "Kanji"
      and T.expected_field(model["tmpls"][1]["qfmt"]) == "Word")
check("a template without a canvas is not given one",
      not T.has_canvas(model["tmpls"][2]["qfmt"]))

# Only the template named is rewired; the rest keep what they check.
model2 = {"tmpls": [
    {"name": "Card 1", "qfmt": T.inject("q", OLD, "Kanji"), "afmt": "x"},
    {"name": "Card 2", "qfmt": T.inject("q2", OLD, "Word"), "afmt": "y"},
]}
T.refresh_model(model2, NEW, {"Card 2": "Expression"})
check("the named template changes field",
      T.expected_field(model2["tmpls"][1]["qfmt"]) == "Expression")
check("and the others do not",
      T.expected_field(model2["tmpls"][0]["qfmt"]) == "Kanji")

# ── The stroke data in the media folder ───────────────────────────────

print("\nstroke data in the media folder")

with tempfile.TemporaryDirectory() as tmp:
    col = FakeCol(tmp)
    path = os.path.join(tmp, media.MEDIA_NAME)

    check("the add-on ships the data", media.available())
    check("installing puts it in the media folder",
          media.install(col) and os.path.exists(path))
    check("under a name Anki syncs and does not call unused",
          media.MEDIA_NAME.startswith("_"))
    check("it expands to something the card can read",
          open(path, encoding="utf-8").read(40).startswith("/*"))

    # Rewriting an identical file would have every sync re-upload half a
    # megabyte for nothing.
    os.utime(path, (0, 0))
    media.install(col)
    check("installing again leaves the file untouched",
          os.path.getmtime(path) == 0)

    media.uninstall(col)
    check("uninstalling removes it", not os.path.exists(path))
    media.uninstall(col)
    check("uninstalling twice is harmless", not os.path.exists(path))

    wired = {"tmpls": [{"qfmt": T.inject("a", CFG, "Kanji"), "afmt": "b"}]}
    plain = {"tmpls": [{"qfmt": T.inject("a", CFG), "afmt": "b"}]}
    check("a template wired to a field keeps the data alive",
          media.any_template_checks(FakeCol(tmp, [wired])))
    check("a canvas with no field does not",
          not media.any_template_checks(FakeCol(tmp, [plain])))
    check("and neither does a collection with no canvas at all",
          not media.any_template_checks(FakeCol(tmp, [{"tmpls": [
              {"qfmt": "a", "afmt": "b"}]}])))

print("\n" + (str(len(FAILURES)) + " failing" if FAILURES else "all passing"))
sys.exit(1 if FAILURES else 0)
