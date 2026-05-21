from __future__ import annotations

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from aqt.utils import askUser, showInfo, tooltip

from .i18n import get_strings
from .template import has_canvas, inject, remove


class DrawingCanvasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self._s: dict[str, str] = get_strings()
        self._models: list = []
        self._setup_ui()
        self._load_notetypes()

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        s = self._s
        self.setWindowTitle(s["dialog_title"])
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)

        # Note-type selector
        nt_row = QHBoxLayout()
        nt_row.addWidget(QLabel(s["select_notetype"]))
        self.nt_combo = QComboBox()
        self.nt_combo.currentIndexChanged.connect(self._refresh_templates)
        nt_row.addWidget(self.nt_combo, 1)
        root.addLayout(nt_row)

        # Template list
        root.addWidget(QLabel(s["templates_label"]))
        self.tmpl_list = QListWidget()
        self.tmpl_list.setAlternatingRowColors(True)
        self.tmpl_list.setMinimumHeight(120)
        root.addWidget(self.tmpl_list)

        # Add / Remove buttons
        act_row = QHBoxLayout()
        self.add_btn = QPushButton(s["add_btn"])
        self.rem_btn = QPushButton(s["remove_btn"])
        self.add_btn.clicked.connect(self._add_canvas)
        self.rem_btn.clicked.connect(self._remove_canvas)
        act_row.addWidget(self.add_btn)
        act_row.addWidget(self.rem_btn)
        root.addLayout(act_row)

        close_btn = QPushButton(s["close_btn"])
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn)

    # ── Data ──────────────────────────────────────────────────────────

    def _load_notetypes(self) -> None:
        self._models = sorted(
            mw.col.models.all(), key=lambda m: m["name"].lower()
        )
        self.nt_combo.blockSignals(True)
        self.nt_combo.clear()
        for m in self._models:
            self.nt_combo.addItem(m["name"])
        self.nt_combo.blockSignals(False)
        if self._models:
            self._refresh_templates(0)

    def _refresh_templates(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._models):
            return
        model = self._models[idx]
        self.tmpl_list.clear()
        for tmpl in model["tmpls"]:
            active = has_canvas(tmpl["qfmt"])
            item = QListWidgetItem(("✓  " if active else "      ") + tmpl["name"])
            item.setData(Qt.ItemDataRole.UserRole, tmpl["name"])
            self.tmpl_list.addItem(item)

    # ── Helpers ───────────────────────────────────────────────────────

    def _selected(self) -> tuple:
        item = self.tmpl_list.currentItem()
        if not item:
            showInfo(self._s["no_template_selected"])
            return None, None
        idx = self.nt_combo.currentIndex()
        if idx < 0:
            return None, None
        model = self._models[idx]
        name  = item.data(Qt.ItemDataRole.UserRole)
        tmpl  = next((t for t in model["tmpls"] if t["name"] == name), None)
        return model, tmpl

    # ── Actions ───────────────────────────────────────────────────────

    def _add_canvas(self) -> None:
        model, tmpl = self._selected()
        if tmpl is None:
            return
        if has_canvas(tmpl["qfmt"]):
            showInfo(self._s["already_added"])
            return
        pkg = __name__.split(".")[0]
        cfg = mw.addonManager.getConfig(pkg) or {}
        tmpl["qfmt"] = inject(tmpl["qfmt"], cfg)
        # Inject into the back template too when it doesn't embed {{FrontSide}}.
        # Without this the canvas is absent from backs that define their own layout.
        if "{{FrontSide}}" not in tmpl["afmt"] and not has_canvas(tmpl["afmt"]):
            tmpl["afmt"] = inject(tmpl["afmt"], cfg)
        mw.col.models.save(model)
        tooltip(self._s["added_ok"])
        self._refresh_templates(self.nt_combo.currentIndex())

    def _remove_canvas(self) -> None:
        model, tmpl = self._selected()
        if tmpl is None:
            return
        if not has_canvas(tmpl["qfmt"]):
            showInfo(self._s["not_present"])
            return
        msg = self._s["confirm_remove"].format(
            tmpl=tmpl["name"], nt=model["name"]
        )
        if not askUser(msg):
            return
        tmpl["qfmt"] = remove(tmpl["qfmt"])
        tmpl["afmt"] = remove(tmpl["afmt"])   # safe no-op if not present
        mw.col.models.save(model)
        tooltip(self._s["removed_ok"])
        self._refresh_templates(self.nt_combo.currentIndex())
