# Stroke reference data

`strokes.js.gz` holds the reference strokes the canvas checks handwriting
against. It is generated from [KanjiVG](https://kanjivg.tagaini.net) by
`tools/build_stroke_data.py` and is not edited by hand:

```sh
curl -LO https://github.com/KanjiVG/kanjivg/releases/download/r20230110/kanjivg-20230110-main.zip
unzip kanjivg-20230110-main.zip
python tools/build_stroke_data.py kanji
```

Current build: KanjiVG r20230110 — 6763 characters (all jōyō and jinmeiyō
kanji, kana, and a long tail of rarer characters), 556 KiB expanded from
364 KiB on disk.

## Why a media file

The add-on expands the gzip into the collection's media folder as
`_kda_strokes.js`, which the card requests at review time. That detour
exists because AnkiDroid and AnkiMobile never run the add-on's Python
code — media is the only channel that reaches them. The leading underscore
keeps Anki from listing the file as unused media, and the whole file is
fetched once per session on desktop (the page persists between cards) and
served from the webview's HTTP cache on mobile.

`drawing/media.py` writes it when a template is first wired to a field and
removes it again once no template uses it.

## Format

One line per character:

```
<character>|<stroke>,<stroke>,…
```

A stroke is a polyline; each of its points is two characters, x then y,
indexes into `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/`,
quantised to 0–63 across KanjiVG's 109×109 em box. Points are the
Ramer-Douglas-Peucker simplification of the flattened Bézier path, so a
straight stroke costs four characters and only bent or curved strokes pay
for more; the runtime resamples each polyline to a fixed number of points
before comparing. Strokes appear in the correct writing order.

The whole file is one JavaScript string rather than an object literal, so
loading it costs a string assignment instead of building thousands of
objects on every card render. Lookups are a substring search for
`"\n" + character + "|"`, which cannot collide with the payload because
stroke data is base64 characters only.

## Licence

KanjiVG is copyright © Ulrich Apel and distributed under
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
`strokes.js.gz` is a derivative work of it and carries the same licence —
see `KANJIVG-LICENSE.txt`. The rest of this add-on is MIT.
