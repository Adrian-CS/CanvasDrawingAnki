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

from . import media
from .i18n import get_strings
from .template import expected_field, has_canvas, inject, remove


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

        # Stroke-checking field. The canvas can compare what is drawn
        # against the character a note field holds; picking that field here
        # is what enables checking for the template being added.
        chk_row = QHBoxLayout()
        chk_row.addWidget(QLabel(s["check_field"]))
        self.field_combo = QComboBox()
        chk_row.addWidget(self.field_combo, 1)
        root.addLayout(chk_row)

        self.check_hint = QLabel(s["check_field_hint"])
        self.check_hint.setWordWrap(True)
        self.check_hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(self.check_hint)

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

    # Fields commonly holding the character itself, across the note types
    # people actually use for this — checked in order, first hit wins.
    _LIKELY_FIELDS = (
        "kanji", "character", "char", "hanzi", "漢字", "字",
        "expression", "word", "front",
    )

    def _refresh_templates(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._models):
            return
        model = self._models[idx]
        self.tmpl_list.clear()
        for tmpl in model["tmpls"]:
            active = has_canvas(tmpl["qfmt"])
            label = ("✓  " if active else "      ") + tmpl["name"]
            field = expected_field(tmpl["qfmt"]) if active else ""
            if field:
                label += f"   ({self._s['check_on_field'].format(field=field)})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, tmpl["name"])
            self.tmpl_list.addItem(item)
        self._refresh_fields(model)

    def _refresh_fields(self, model) -> None:
        names = [f["name"] for f in model["flds"]]
        self.field_combo.clear()
        self.field_combo.addItem(self._s["check_field_none"], "")
        for name in names:
            self.field_combo.addItem(name, name)
        # Pre-select an obvious candidate so the common case is one click,
        # while leaving "no checking" as the outcome when nothing fits.
        lowered = {n.lower(): n for n in names}
        for guess in self._LIKELY_FIELDS:
            if guess in lowered:
                self.field_combo.setCurrentText(lowered[guess])
                break
        if not media.available():
            # An add-on copy built without the data file can still draw;
            # it just can't check, so don't offer a choice that won't work.
            self.field_combo.setCurrentIndex(0)
            self.field_combo.setEnabled(False)
            self.check_hint.setText(self._s["check_no_data"])

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
        field = self.field_combo.currentData() or ""
        if field and not media.install(mw.col):
            # Without the reference data the canvas would offer checking it
            # cannot perform, so fall back to a plain canvas and say so.
            showInfo(self._s["check_install_failed"])
            field = ""
        tmpl["qfmt"] = inject(tmpl["qfmt"], cfg, field)
        # Inject into the back template too when it doesn't embed {{FrontSide}}.
        # Without this the canvas is absent from backs that define their own layout.
        if "{{FrontSide}}" not in tmpl["afmt"] and not has_canvas(tmpl["afmt"]):
            tmpl["afmt"] = inject(tmpl["afmt"], cfg, field)
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
        # The reference data is half a megabyte of synced media; once the
        # last template that could use it is gone, so is the reason to keep
        # it in the collection.
        if not media.any_template_checks(mw.col):
            media.uninstall(mw.col)
        tooltip(self._s["removed_ok"])
        self._refresh_templates(self.nt_combo.currentIndex())
