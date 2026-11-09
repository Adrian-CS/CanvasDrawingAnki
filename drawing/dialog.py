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
from .template import (
    expected_field,
    has_canvas,
    inject,
    refresh_model,
    remove,
)


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
        self.tmpl_list.currentItemChanged.connect(self._template_selected)
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

        # Settings are baked into the block when it is injected, so without
        # this every change to the configuration means removing and
        # re-adding the canvas on each template by hand.
        self.upd_btn = QPushButton(s["update_btn"])
        self.upd_btn.setToolTip(s["update_confirm_plain"].format(n="…", m="…"))
        self.upd_btn.clicked.connect(self._update_canvases)
        root.addWidget(self.upd_btn)

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
        self._refresh_fields(model, self._selected_field())

    def _selected_field(self):
        """What the selected template checks against, or None if unknown."""
        model, tmpl = self._selected(quiet=True)
        if tmpl is None or not has_canvas(tmpl["qfmt"]):
            return None
        return expected_field(tmpl["qfmt"])

    def _template_selected(self, *_args) -> None:
        idx = self.nt_combo.currentIndex()
        if 0 <= idx < len(self._models):
            self._refresh_fields(self._models[idx], self._selected_field())

    def _refresh_fields(self, model, current: str | None = None) -> None:
        names = [f["name"] for f in model["flds"]]
        self.field_combo.clear()
        self.field_combo.addItem(self._s["check_field_none"], "")
        for name in names:
            self.field_combo.addItem(name, name)
        # A template that already has a canvas says what it checks against;
        # showing a guess instead would be telling the user something
        # untrue about the template in front of them.
        if current and current in names:
            self.field_combo.setCurrentText(current)
        elif current == "":
            self.field_combo.setCurrentIndex(0)
        else:
            # Nothing to go on: pre-select an obvious candidate so the
            # common case is one click, leaving "no checking" when nothing
            # fits.
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

    def _selected(self, quiet: bool = False) -> tuple:
        item = self.tmpl_list.currentItem()
        if not item:
            if not quiet:
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

    def _update_canvases(self) -> None:
        """Rewrite every canvas in the collection with the current config.

        Each template keeps the field it checks against; the one selected
        in the list takes whatever the field selector shows, so a field can
        be changed without dismantling the canvas and building it again.
        """
        pkg = __name__.split(".")[0]
        cfg = mw.addonManager.getConfig(pkg) or {}

        models = [m for m in self._models
                  if any(has_canvas(t["qfmt"]) or has_canvas(t["afmt"])
                         for t in m["tmpls"])]
        total = sum(sum(bool(has_canvas(t[side]))
                        for t in m["tmpls"] for side in ("qfmt", "afmt"))
                    for m in models)
        if not total:
            showInfo(self._s["update_none"])
            return

        # The selected template is the one the field selector is showing,
        # so that is the only one allowed to change what it checks against.
        sel_model, sel_tmpl = self._selected(quiet=True)
        override = None
        if sel_tmpl is not None and has_canvas(sel_tmpl["qfmt"]):
            chosen = self.field_combo.currentData() or ""
            if chosen != expected_field(sel_tmpl["qfmt"]):
                override = (sel_model["name"], sel_tmpl["name"], chosen)

        if override:
            msg = self._s["update_confirm"].format(
                n=total, m=len(models), tmpl=override[1],
                field=override[2] or self._s["check_field_none"])
        else:
            msg = self._s["update_confirm_plain"].format(n=total, m=len(models))
        if not askUser(msg):
            return

        if override and override[2] and not media.install(mw.col):
            showInfo(self._s["check_install_failed"])
            override = (override[0], override[1], "")

        done = 0
        for model in models:
            fields = ({override[1]: override[2]}
                      if override and override[0] == model["name"] else None)
            done += refresh_model(model, cfg, fields)
            mw.col.models.save(model)

        # A field may have been dropped by this, which can leave the stroke
        # data with nothing using it.
        if not media.any_template_checks(mw.col):
            media.uninstall(mw.col)

        tooltip(self._s["update_ok"].format(n=done))
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
