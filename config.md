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
