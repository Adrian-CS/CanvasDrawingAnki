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
