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
        "check_field": "Check strokes against field:",
        "check_field_none": "— don't check strokes —",
        "check_field_hint": (
            "Pick the field holding the character being practised. The canvas "
            "then compares each stroke against its reference shape, order and "
            "direction. A field holding a word gets one canvas per character. "
            "Applies to templates added from now on."
        ),
        "check_on_field": "checking: {field}",
        "check_no_data": (
            "Stroke reference data is missing from this add-on copy, so "
            "stroke checking is unavailable."
        ),
        "check_install_failed": (
            "The stroke reference data could not be written to the media "
            "folder. The canvas was added without stroke checking."
        ),
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
        "check_field": "Comprobar trazos con el campo:",
        "check_field_none": "— no comprobar trazos —",
        "check_field_hint": (
            "Elige el campo que contiene el carácter que estás practicando. El "
            "canvas comparará cada trazo con su forma, orden y dirección de "
            "referencia. Si el campo contiene una palabra, se añade un canvas "
            "por carácter. Se aplica a las plantillas que añadas a partir de ahora."
        ),
        "check_on_field": "comprobando: {field}",
        "check_no_data": (
            "Esta copia del complemento no incluye los datos de trazos de "
            "referencia, así que la comprobación no está disponible."
        ),
        "check_install_failed": (
            "No se pudieron escribir los datos de trazos en la carpeta de "
            "medios. El canvas se añadió sin comprobación de trazos."
        ),
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
        "check_field": "筆画を照合するフィールド:",
        "check_field_none": "— 照合しない —",
        "check_field_hint": (
            "練習する文字が入っているフィールドを選んでください。キャンバスが各筆画を"
            "手本の形・筆順・方向と照合します。単語が入っている場合は1文字につき1つ"
            "キャンバスが並びます。これ以降に追加するテンプレートに適用されます。"
        ),
        "check_on_field": "照合: {field}",
        "check_no_data": (
            "このアドオンには筆画データが含まれていないため、照合は利用できません。"
        ),
        "check_install_failed": (
            "筆画データをメディアフォルダに書き込めませんでした。"
            "キャンバスは照合なしで追加されました。"
        ),
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
