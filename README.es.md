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
- **Comprobación de trazos** *(opcional)* — compara lo que escribes con el
  carácter esperado: forma, posición, orden y dirección de cada trazo, sobre
  la marcha o cuando tú lo pidas. Si el campo contiene una palabra, se añade
  un canvas por carácter. También funciona en móvil.
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

## Comprobar que escribes el carácter correcto

Opcionalmente, el canvas puede comprobar tu escritura contra el carácter del
que trata la tarjeta, en lugar de dejarte comparar a ojo.

1. En **Herramientas → Canvas de dibujo…**, antes de pulsar **Añadir Canvas**,
   elige en **Comprobar trazos con el campo** el campo que contiene el carácter
   (`Kanji`, `Carácter`, `Expression`…). Se preselecciona un candidato probable.
2. Pulsa **Añadir Canvas**. Los datos de referencia se copian a la carpeta de
   medios de tu colección, desde donde se sincronizan con tu móvil.
3. Durante la revisión, el botón ✓ junto al canvas activa y desactiva la
   comprobación.

Lo que te dice, trazo a trazo:

| | |
|---|---|
| trazo rojo | trazo incorrecto, o con una longitud claramente distinta |
| trazo ámbar | trazo correcto, pero fuera de orden o en dirección invertida |
| contorno punteado | dónde debería haber ido ese trazo |
| línea bajo el canvas | el veredicto — `¡Correcto! Los 13 trazos`, `9 de 13 trazos correctos · trazo 4: fuera de orden`, `Faltan 1 trazo(s)` |

Si el campo contiene una palabra en lugar de un solo carácter, obtienes un
canvas por carácter, uno al lado del otro y cada uno comprobado contra el
suyo — 図書館 da tres. Las lecturas furigana entre corchetes se ignoran, así
que 漢字[かんじ] sigue dando dos canvas y no cinco.

Por defecto cada trazo se juzga al levantar el dedo. Pon `check_mode` en
`"manual"` si prefieres escribir el carácter entero sin interrupciones y pulsar
**Comprobar** al terminar. En ambos casos, el reverso muestra el veredicto
completo de lo que escribiste.

La comprobación está desactivada hasta que elijas un campo, y sus botones no
aparecen en plantillas que no tengan ninguno — para la práctica de dibujo sin
más no cambia nada.

Los datos de trazos de referencia provienen de
[KanjiVG](https://kanjivg.tagaini.net) y cubren 6763 caracteres: todos los
kanji jōyō y jinmeiyō, los kana y muchos caracteres poco frecuentes. Lo que
quede fuera (hangul, letras latinas) simplemente avisa de que no hay
referencia, y el dibujo sigue funcionando.

Consulta [`config.md`](config.md) para saber qué puede y qué no puede
detectar la comprobación.

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
| `persist_drawing` | `true` | Mantener el dibujo al girar a la respuesta |
| `restore_after_undo` | `true` | Restaurar el dibujo si se vuelve a mostrar la misma pregunta |
| `keep_window_seconds` | `90` | Durante cuánto tiempo sigue disponible esa restauración |
| `check_strokes` | `false` | Si la comprobación de trazos empieza activada |
| `check_mode` | `"live"` | `"live"` (juzga cada trazo) o `"manual"` (juzga al pedirlo) |
| `check_tolerance` | `1.0` | Cuánta manga ancha da la comparación — súbelo para aceptar escritura más tosca |

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

Los datos de trazos de referencia de `drawing/data/` derivan de
[KanjiVG](https://kanjivg.tagaini.net) (© Ulrich Apel) y se distribuyen bajo
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), como exige esa
licencia — véase
[`drawing/data/KANJIVG-LICENSE.txt`](drawing/data/KANJIVG-LICENSE.txt).
