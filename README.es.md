# Kanji Drawing Canvas

> También disponible en [English](README.md) · [日本語](README.ja.md)

Un complemento para [Anki](https://apps.ankiweb.net/) que añade un canvas de
dibujo a libre mano en cualquier tipo de nota, para practicar la escritura de
kanjis, hangul o cualquier carácter directamente durante la revisión de tus
tarjetas — tanto en escritorio **como** en móvil.

---

## Características

- **Canvas separado** añadido debajo del contenido existente de la carta — sin
  solapamiento ni cambios en el layout de tu plantilla.
- **Cuadrículas de práctica**: 田字格 (4 cuadrantes), 米字格 (4 cuadrantes +
  diagonales) o sin cuadrícula.
- Botón **Deshacer** trazo a trazo y botón **Borrar**.
- **Contador de trazos** — útil para verificar el número de trazos de un kanji.
- **Funciona en móvil** (AnkiDroid / AnkiMobile) mediante HTML5 Canvas +
  Pointer Events estándar — no se necesita complemento en el lado móvil.
- **Idioma de la interfaz detectado automáticamente**: inglés, español o
  japonés, según el idioma del dispositivo.
- No destructivo: el canvas se puede eliminar de cualquier plantilla en
  cualquier momento desde el mismo diálogo.

---

## Requisitos

| Componente | Versión mínima |
|------------|----------------|
| Anki (escritorio) | 2.1.45 |
| AnkiDroid | 2.15 |
| AnkiMobile | cualquier versión reciente |

---

## Instalación

### Desde AnkiWeb *(recomendado)*

1. En Anki ve a **Herramientas → Complementos → Obtener complementos**.
2. Introduce el código del complemento *(disponible tras la revisión de AnkiWeb)*.
3. Reinicia Anki.

### Manual

1. Descarga o clona este repositorio.
2. Copia la carpeta `kanjiDrawingAnki` en el directorio de complementos de Anki
   (`Herramientas → Complementos → Abrir carpeta de complementos`).
3. Reinicia Anki.

---

## Uso

1. Abre **Herramientas → Canvas de dibujo…**
2. Selecciona el **tipo de nota** que quieres modificar en el desplegable.
3. Selecciona una **plantilla** en la lista (normalmente *Carta 1*) y haz clic
   en **Añadir Canvas**.
4. Estudia con normalidad — el canvas aparecerá en la parte inferior del frente
   de la carta.

**Flujo de estudio recomendado:**

```
Frente: leer el significado / lectura  →  dibujar el carácter  →  girar  →  comparar
```

**Para eliminar** el canvas: abre el diálogo, selecciona la misma plantilla y
haz clic en **Eliminar Canvas**.

---

## Configuración

Ve a **Herramientas → Complementos**, selecciona *Kanji Drawing Canvas* y haz
clic en **Configuración**.

| Clave | Valor por defecto | Descripción |
|-------|-------------------|-------------|
| `canvas_size` | `300` | Lado del canvas en píxeles |
| `grid_type` | `"tian"` | `"tian"` (田), `"mi"` (米) o `"none"` |
| `stroke_width` | `3` | Grosor del pincel en píxeles |
| `stroke_color` | `"#1a1a1a"` | Color del trazo (cualquier valor CSS) |
| `grid_color` | `"#cccccc"` | Color de las líneas guía |
| `background_color` | `"#ffffff"` | Color de fondo del canvas |

Tras cambiar la configuración, **elimina y vuelve a añadir** el canvas en cada
plantilla afectada para aplicar los nuevos valores.

---

## Cómo funciona

El complemento añade un pequeño bloque `<div>` + `<script>` autocontenido,
entre comentarios marcadores especiales, al final de la plantilla *frontal* del
tipo de nota elegido. No se crean nuevos campos ni se modifican datos de las
tarjetas. El estado del canvas es efímero — se reinicia en cada nueva carta y
en cada giro, como una hoja de práctica física.

---

## Licencia

[MIT](LICENSE)
