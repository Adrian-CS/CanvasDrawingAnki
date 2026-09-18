# Kanji Drawing Canvas

> Also available in [Español](README.es.md) · [日本語](README.ja.md)

An [Anki](https://apps.ankiweb.net/) add-on that injects a freehand drawing
canvas into any note type, so you can practise writing kanji, hangul, or any
character directly inside your flashcard review — on desktop **and** mobile.

---

## Features

- **Separate canvas block** appended below the existing card content — no
  overlap, no layout changes to your template.
- **Practice grids**: 田字格 (4-quadrant), 米字格 (4-quadrant + diagonals),
  or plain (no grid).
- **Undo** stroke by stroke and **Clear** button.
- **Stroke counter** — handy for verifying kanji stroke count.
- **Stroke checking** *(optional)* — compares what you write against the
  expected character: shape, position, stroke order and stroke direction,
  live as you write or on demand. A field holding a word gets one canvas
  per character. Works on mobile too.
- **Works on mobile** (AnkiDroid / AnkiMobile) via standard HTML5 Canvas +
  Pointer Events — no add-on required on the mobile side.
- **Auto-detected UI language**: English, Spanish, or Japanese, following the
  browser/app locale of the reviewing device.
- Non-destructive: the canvas block can be removed from any template at any
  time through the same dialog.

---

## Requirements

| Component | Minimum version |
|-----------|----------------|
| Anki (desktop) | 2.1.45 |
| AnkiDroid | 2.15 |
| AnkiMobile | any recent version |

---

## Installation

### From AnkiWeb *(recommended)*

1. In Anki go to **Tools → Add-ons → Get Add-ons**.
2. Enter the add-on code *(published after AnkiWeb review)*.
3. Restart Anki.

### Manual

1. Download or clone this repository.
2. Copy the `kanjiDrawingAnki` folder into your Anki add-ons directory
   (`Tools → Add-ons → Open Add-ons Folder`).
3. Restart Anki.

---

## Usage

1. Open **Tools → Drawing Canvas…**
2. Select the **note type** you want to modify from the drop-down.
3. Select a **template** in the list (usually *Card 1*) and click **Add Canvas**.
4. Study normally — the canvas will appear at the bottom of the card front.

**Recommended study flow:**

```
Front: read the meaning / reading  →  draw the character  →  flip  →  compare
```

**To remove** the canvas: open the dialog, select the same template, click
**Remove Canvas**.

---

## Checking that you wrote the right character

Optionally, the canvas can check your writing against the character the card
is about, rather than leaving you to compare by eye.

1. In **Tools → Drawing Canvas…**, before clicking **Add Canvas**, set
   **Check strokes against field** to the field holding the character
   (`Kanji`, `Character`, `Expression`…). A likely field is pre-selected.
2. Click **Add Canvas**. The reference data is copied into your collection's
   media folder, from where it syncs to your phone.
3. While reviewing, the ✓ button next to the canvas turns checking on and off.

What it tells you, per stroke:

| | |
|---|---|
| red stroke | wrong stroke, or clearly the wrong length |
| amber stroke | right stroke, but out of order or drawn backwards |
| dashed outline | where that stroke should have gone |
| the wording | *out of order*, *drawn backwards*, *right shape, wrong place*, *wrong length*, *wrong shape* — the verdict names the mistake |
| line below the canvas | the verdict — `Correct — all 13 strokes`, `9 of 13 strokes correct · stroke 4: out of order`, `1 stroke(s) missing` |

If the field holds a word rather than a single character, you get one
canvas per character, side by side and each checked against its own
character — 図書館 gives three. Furigana readings in brackets are ignored,
so 漢字[かんじ] still gives two canvases and not five.

By default each stroke is judged as you lift the pen. Set `check_mode` to
`"manual"` if you would rather write the whole character undisturbed and
press **Check** when you are done. Either way the answer side shows the full
verdict for what you wrote.

Checking is off until you pick a field, and the buttons for it stay hidden on
templates that have none — nothing changes for plain drawing practice.

Reference stroke data comes from [KanjiVG](https://kanjivg.tagaini.net) and
covers 6763 characters: all jōyō and jinmeiyō kanji, kana, and many rarer
characters. Anything outside it (hangul, Latin letters) simply reports that
there is no reference, and drawing keeps working.

See [`config.md`](config.md) for what the checker can and cannot tell you.

---

## Configuration

Go to **Tools → Add-ons**, select *Kanji Drawing Canvas*, click **Config**.

| Key | Default | Description |
|-----|---------|-------------|
| `canvas_size` | `300` | Canvas side length in pixels |
| `grid_type` | `"tian"` | `"tian"` (田), `"mi"` (米), or `"none"` |
| `stroke_width` | `3` | Brush width in pixels |
| `stroke_color` | `"#1a1a1a"` | Stroke colour (any CSS value) |
| `grid_color` | `"#cccccc"` | Guide-line colour |
| `background_color` | `"#ffffff"` | Canvas background colour |
| `persist_drawing` | `true` | Keep the drawing when flipping to the answer |
| `restore_after_undo` | `true` | Restore the drawing when the same question is shown again |
| `keep_window_seconds` | `90` | How long that restore stays available |
| `check_strokes` | `false` | Whether stroke checking starts out on |
| `check_mode` | `"live"` | `"live"` (judge each stroke) or `"manual"` (judge on demand) |
| `check_tolerance` | `1.0` | How forgiving stroke matching is — raise to accept rougher writing |

After changing config values, **remove and re-add** the canvas on each affected
template to apply the new settings.

---

## How it works

The add-on appends a small, self-contained `<div>` + `<script>` block between
special marker comments at the end of the *front* template of the chosen note
type. No new fields are created and no card data is modified. The canvas state
is ephemeral — it resets on every new card and every card flip, exactly like a
physical practice sheet.

---

## License

[MIT](LICENSE)

The stroke reference data in `drawing/data/` is derived from
[KanjiVG](https://kanjivg.tagaini.net) (© Ulrich Apel) and is distributed
under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), as
that licence requires — see
[`drawing/data/KANJIVG-LICENSE.txt`](drawing/data/KANJIVG-LICENSE.txt).
