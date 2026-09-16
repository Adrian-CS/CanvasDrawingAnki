"""Installing the stroke-reference data into the collection media folder.

Stroke checking needs KanjiVG-derived reference data available to the card
itself, including on AnkiDroid and AnkiMobile where none of this add-on's
Python code runs. The only channel that reaches those is the collection's
media folder, so the data ships gzipped inside the add-on and is expanded
into the media folder as ``_kda_strokes.js`` on demand.

The leading underscore matters: Anki treats such files as add-on assets,
syncing them to every device while keeping them out of the "unused media"
report that would otherwise offer to delete them.
"""

from __future__ import annotations

import gzip
import os

MEDIA_NAME = "_kda_strokes.js"
_SOURCE = os.path.join(os.path.dirname(__file__), "data", "strokes.js.gz")


def available() -> bool:
    """Whether this add-on copy ships the reference data at all."""
    return os.path.exists(_SOURCE)


def _payload() -> bytes:
    with gzip.open(_SOURCE, "rb") as fh:
        return fh.read()


def install(col) -> bool:
    """Write the data file into the media folder if it isn't there already.

    Returns True when the file is in place afterwards. Rewriting an
    identical file would make the next sync re-upload half a megabyte for
    nothing, so an up-to-date copy is left untouched.
    """
    if not available():
        return False
    data = _payload()
    path = os.path.join(col.media.dir(), MEDIA_NAME)
    try:
        if os.path.exists(path) and os.path.getsize(path) == len(data):
            with open(path, "rb") as fh:
                if fh.read() == data:
                    return True
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        return False
    return True


def uninstall(col) -> None:
    """Drop the data file — used once no template checks strokes any more."""
    path = os.path.join(col.media.dir(), MEDIA_NAME)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def any_template_checks(col) -> bool:
    """True when some template still has a canvas wired to a field."""
    from .template import expected_field

    for model in col.models.all():
        for tmpl in model["tmpls"]:
            if expected_field(tmpl["qfmt"]) or expected_field(tmpl["afmt"]):
                return True
    return False
