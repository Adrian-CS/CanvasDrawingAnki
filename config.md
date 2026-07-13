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

Note: pressing Undo while still looking at a card's answer (before grading
it) does not return you to its question — that's normal Anki behaviour
(there is nothing to undo about a card you haven't graded yet), and this
add-on has no control over which side Anki decides to display.
