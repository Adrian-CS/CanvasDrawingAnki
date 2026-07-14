from aqt import mw
from aqt.qt import QAction

from .drawing.i18n import get_strings


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
