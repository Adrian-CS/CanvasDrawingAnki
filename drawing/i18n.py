from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "menu_action": "Drawing Canvas…",
        "dialog_title": "Kanji Drawing Canvas",
        "select_notetype": "Note type:",
        "templates_label": "Templates  (✓ = canvas active):",
        "add_btn": "Add Canvas",
        "remove_btn": "Remove Canvas",
        "close_btn": "Close",
        "already_added": "The canvas is already added to this template.",
        "not_present": "The canvas is not present in this template.",
        "added_ok": "Canvas added successfully.",
        "removed_ok": "Canvas removed successfully.",
        "no_template_selected": "Please select a template first.",
        "confirm_remove": "Remove the drawing canvas from '{tmpl}' in '{nt}'?",
    },
    "es": {
        "menu_action": "Canvas de dibujo…",
        "dialog_title": "Canvas de Dibujo Kanji",
        "select_notetype": "Tipo de nota:",
        "templates_label": "Plantillas  (✓ = canvas activo):",
        "add_btn": "Añadir Canvas",
        "remove_btn": "Eliminar Canvas",
        "close_btn": "Cerrar",
        "already_added": "El canvas ya está añadido a esta plantilla.",
        "not_present": "El canvas no está presente en esta plantilla.",
        "added_ok": "Canvas añadido correctamente.",
        "removed_ok": "Canvas eliminado correctamente.",
        "no_template_selected": "Selecciona una plantilla primero.",
        "confirm_remove": "¿Eliminar el canvas de dibujo de '{tmpl}' en '{nt}'?",
    },
    "ja": {
        "menu_action": "描画キャンバス…",
        "dialog_title": "漢字描画キャンバス",
        "select_notetype": "ノートタイプ:",
        "templates_label": "テンプレート（✓ = キャンバス有効）:",
        "add_btn": "キャンバスを追加",
        "remove_btn": "キャンバスを削除",
        "close_btn": "閉じる",
        "already_added": "このテンプレートにはすでにキャンバスが追加されています。",
        "not_present": "このテンプレートにキャンバスはありません。",
        "added_ok": "キャンバスを追加しました。",
        "removed_ok": "キャンバスを削除しました。",
        "no_template_selected": "先にテンプレートを選択してください。",
        "confirm_remove": "'{nt}' の '{tmpl}' から描画キャンバスを削除しますか？",
    },
}


def _detect_lang() -> str:
    try:
        from anki.lang import current_lang  # type: ignore
        if current_lang:
            return current_lang[:2].lower()
    except Exception:
        pass
    try:
        from aqt import mw  # type: ignore
        lang = mw.pm.meta.get("defaultLang", "en")
        return lang[:2].lower()
    except Exception:
        pass
    return "en"


def get_strings() -> dict[str, str]:
    lang = _detect_lang()
    return STRINGS.get(lang, STRINGS["en"])
