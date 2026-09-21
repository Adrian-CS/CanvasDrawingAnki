# Configuration

After changing any value, open **Tools → Drawing Canvas…**, remove the canvas
from the affected template, and re-add it so the new values take effect.

**`canvas_size`** *(integer, default `300`)*
Side length of the square canvas in pixels.

**`grid_type`** *(string, default `"tian"`)*
Practice grid drawn behind your strokes.
- `"tian"` — 田字格: two dashed lines dividing the canvas into four quadrants.
- `"mi"` — 米字格: like *tian* plus two diagonal dashed lines.
- `"none"` — no grid.

**`stroke_width`** *(integer, default `3`)*
Brush width in pixels.

**`stroke_color`** *(string, default `"#1a1a1a"`)*
Stroke colour. Accepts any CSS colour value (`"#ff0000"`, `"red"`, `"rgb(0,0,0)"`, …).

**`grid_color`** *(string, default `"#aaaaaa"`)*
Guide-line colour.

**`background_color`** *(string, default `"#ffffff"`)*
Canvas background colour.

**`persist_drawing`** *(boolean, default `true`)*
When `true`, the drawing is preserved when you flip the card to the answer side,
so you can compare what you wrote against the correct character.
When `false`, the canvas is always blank on the answer side.

**`restore_after_undo`** *(boolean, default `true`)*
Controls what happens to the front-side drawing when the SAME card's
question is shown again without it being a new card — e.g. exiting and
re-entering the deck mid-review, or Undo in the specific case where it
resurfaces a card's question again.
When `true`, whatever was drawn is restored as-is.
When `false`, the canvas is cleared, exactly as if it were a new card.
Both settings can also be toggled live during review with the Keep / Fresh
button next to the canvas, which overrides this default for the current
device until changed again.

**`keep_window_seconds`** *(integer, default `90`)*
How recently a card's front must have last been drawn on for `restore_after_undo` /
Keep to bring that drawing back. Long enough to cover a quick Undo or
exiting/re-entering the deck, short enough to exclude:
- Anki's "Again" bringing the same card back for another attempt later in
  the same session (its shortest learning step is about a minute), where
  you want a blank canvas to redraw on, not your previous (wrong) attempt.
- A previous day's drawing coming back when spaced repetition resurfaces
  the same card again later.

Raise this if you routinely step away for longer between exiting and
re-entering the deck than you'd want the canvas to forget; lower it if
your shortest learning/relearning step is less than 90 seconds and
"Again" is still bringing old drawings back.

Note: pressing Undo while still looking at a card's answer (before grading
it) does not return you to its question — that's normal Anki behaviour
(there is nothing to undo about a card you haven't graded yet), and this
add-on has no control over which side Anki decides to display.

"Same card" is detected from the card's own rendered content, not a
card id, since AnkiMobile doesn't run this add-on's Python code — this
works identically on desktop and mobile, but two cards with byte-for-byte
identical front content would (harmlessly) be treated as the same card.

The canvas tells the front and back apart by checking for Anki's default
`<hr id=answer>` marker in the answer template. If your back template
both skips `{{FrontSide}}` and has removed that marker, the canvas can't
detect it and will behave like the front there too.

---

## Stroke checking

The canvas can compare what you write against the character the card is
about — stroke by stroke, including order and direction. It needs a note
field holding that character: pick it in **Tools → Drawing Canvas…** when
adding the canvas to a template ("Check strokes against field"). Without a
field chosen, none of the settings below have any effect and no extra
button appears.

Reference shapes come from KanjiVG, expanded into your collection's media
folder as `_kda_strokes.js` the first time a template is wired to a field
and removed again when the last one goes. It syncs to your phone like any
other media file, which is what makes checking work on AnkiDroid and
AnkiMobile, where add-ons do not run.

**`check_strokes`** *(boolean, default `false`)*
Whether checking starts out on. The ✓ button next to the canvas toggles it
live and that choice, like Keep / Fresh, overrides this default on that
device until changed again.

**`check_mode`** *(string, default `"live"`)*
- `"live"` — every stroke is judged the moment you lift the pen.
- `"manual"` — nothing is judged until you press **Check**, so you can
  write the whole character undisturbed.

Either way, a stroke that went wrong turns red or amber and the shape it
should have had is drawn over your writing as a dashed outline, so there is
always something to correct towards. And either way the answer side shows
the full verdict for what you wrote on the question side.

The verdict names the mistake rather than just calling the stroke wrong:

| | |
|---|---|
| *out of order* | the right stroke, drawn too early |
| *drawn backwards* | the right stroke, drawn end to start |
| *right shape, wrong place* | the shape is right, it is not where it belongs |
| *wrong length* | the right shape, far too long or too short |
| *wrong shape* | not that stroke |
| *extra stroke* | more strokes than the character has |

**`check_tolerance`** *(number, default `1.0`)*
Multiplies how far a stroke may sit from its reference shape before it
counts as wrong. The default accepts writing that is half-size, in a
corner, rotated by about five degrees or visibly shaky, while still
telling apart characters as close as 未 and 末. Raise it (`1.3`) if your
handwriting keeps being marked wrong; lower it (`0.8`) to be held to a
stricter standard.

**More than one character**

A field holding a word gets one canvas per character, side by side in
writing order, each checked against its own character: 図書館 gives three,
食べる gives three (KanjiVG covers kana too). Furigana readings in square
brackets are ignored, so a field holding 漢字[かんじ] still gives two
canvases and not five. The canvases share the width and wrap onto another
line when they no longer fit, and the preference buttons move to a row of
their own below them instead of being repeated under each canvas.

A field holding a whole sentence would fill the card with canvases, so at
most eight characters are taken; the rest are left out.

**How big you write is not a mistake**

Almost nobody fills the em box the reference fonts use, so the canvas works
out the size and position you are actually writing at and judges the strokes
in that frame — from the first stroke onwards, and down to about 40% of the
box. It also remembers the last measurement per device, so a character
starts out in the frame you have been writing in rather than assuming you
fill the box.

While a character is unfinished that frame is fitted to what you have drawn
so far, which is what stops a small character being called wrong before
there is enough of it to measure. Once the character is finished it is
judged in the frame its own box implies: allowing the size and position to
float freely at that point would also let it absorb part of what separates
土 from 士.

The dashed outline of an expected stroke is drawn in that same frame, so it
lands on top of your writing at your size instead of floating at the
reference font's.

Some limits are worth knowing about:

- Stroke checking is shape matching, not recognition. It is good at
  catching a wrong stroke order, a stroke drawn backwards, a missing
  stroke and a genuinely different character; it cannot grade calligraphy,
  and a character written very differently from the reference (heavily
  slanted, or in a cursive style) may be marked wrong although a human
  would read it fine.
- Characters KanjiVG has no entry for — hangul, Latin, and the rarest
  kanji — simply report that there is no reference; drawing still works.
