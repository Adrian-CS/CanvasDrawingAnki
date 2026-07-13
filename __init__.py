from aqt import gui_hooks, mw
from aqt.qt import QAction

from .drawing.i18n import get_strings


def _inject_card_context(text: str, card, kind: str) -> str:
    # Gives the canvas script (drawing/template.py) the real card id and
    # render kind, so it can tell "this card's front shown again" (undo,
    # exiting/re-entering the deck mid-review) apart from "a new card" —
    # a distinction a pure front/back toggle can't make on its own.
    script = f'<script>window.__kdaCid={card.id};window.__kdaKind="{kind}";</script>'
    return script + text


def _open_dialog() -> None:
    from .drawing.dialog import DrawingCanvasDialog
    dlg = DrawingCanvasDialog(mw)
    dlg.exec()


def _setup_menu() -> None:
    s = get_strings()
    action = QAction(s["menu_action"], mw)
    action.triggered.connect(_open_dialog)
    mw.form.menuTools.addAction(action)


_setup_menu()
gui_hooks.card_will_show.append(_inject_card_context)
