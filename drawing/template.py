from __future__ import annotations

import re

MARKER_START = "<!-- KANJI-DRAW-START -->"
MARKER_END = "<!-- KANJI-DRAW-END -->"

# Self-contained canvas script. Config is read from data-* attributes on the
# anchor div so the JS never needs to be regenerated when settings change.
_CANVAS_JS = r"""(function () {
  var a = document.getElementById('kda-anchor');
  if (!a || document.getElementById('kda-wrap')) { return; }

  var d  = a.dataset;
  var SZ = parseInt(d.size, 10) || 300;
  var GR = d.grid || 'tian';
  var SW = parseFloat(d.sw) || 3;
  var SC = d.sc  || '#1a1a1a';
  var GC = d.gc  || '#cccccc';
  var BG = d.bg  || '#ffffff';

  // UI labels – auto-detected from browser locale so the card works on any
  // platform without re-injection when the language changes.
  var LABELS = {
    en: ['Clear', 'Undo', 'Strokes'],
    es: ['Borrar', 'Deshacer', 'Trazos'],
    ja: ['クリア', '元に戻す', '画数']
  };
  var lc = (navigator.language || 'en').slice(0, 2);
  var L  = LABELS[lc] || LABELS['en'];

  var strokes = [], cur = [], dn = false;

  /* ── DOM ─────────────────────────────────────────────────────────── */
  var wrap = document.createElement('div');
  wrap.id = 'kda-wrap';
  wrap.style.cssText =
    'margin:16px auto;text-align:center;' +
    '-webkit-user-select:none;user-select:none;';

  var cvs = document.createElement('canvas');
  cvs.width  = SZ;
  cvs.height = SZ;
  cvs.style.cssText =
    'display:block;margin:0 auto;border:2px solid #888;border-radius:6px;' +
    'cursor:crosshair;touch-action:none;' +
    'max-width:min(100%,' + SZ + 'px);background:' + BG + ';';

  var bar = document.createElement('div');
  bar.style.cssText =
    'margin-top:8px;display:flex;justify-content:center;' +
    'gap:8px;align-items:center;flex-wrap:wrap;';

  function mkBtn(label, fn) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText =
      'padding:5px 16px;font-size:14px;border-radius:4px;' +
      'border:1px solid #999;background:#f5f5f5;cursor:pointer;';
    b.addEventListener('click', fn);
    return b;
  }

  var clrBtn = mkBtn(L[0], function () { strokes = []; redraw(); tick(); });
  var undBtn = mkBtn(L[1], function () {
    if (strokes.length) { strokes.pop(); redraw(); tick(); }
  });
  var ctr = document.createElement('span');
  ctr.style.cssText =
    'font-size:13px;color:#777;min-width:70px;display:inline-block;';

  bar.appendChild(clrBtn);
  bar.appendChild(undBtn);
  bar.appendChild(ctr);
  wrap.appendChild(cvs);
  wrap.appendChild(bar);
  a.insertAdjacentElement('afterend', wrap);

  /* ── Canvas ──────────────────────────────────────────────────────── */
  var ctx = cvs.getContext('2d');

  function drawGrid() {
    if (GR === 'none') { return; }
    ctx.save();
    ctx.strokeStyle = GC;
    ctx.lineWidth   = 0.75;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(SZ / 2, 0);    ctx.lineTo(SZ / 2, SZ); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, SZ / 2);    ctx.lineTo(SZ, SZ / 2); ctx.stroke();
    if (GR === 'mi') {
      ctx.beginPath(); ctx.moveTo(0, 0);   ctx.lineTo(SZ, SZ); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(SZ, 0);  ctx.lineTo(0,  SZ); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  function paintStroke(pts) {
    if (pts.length < 2) { return; }
    ctx.save();
    ctx.strokeStyle = SC;
    ctx.lineWidth   = SW;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (var i = 1; i < pts.length; i++) { ctx.lineTo(pts[i].x, pts[i].y); }
    ctx.stroke();
    ctx.restore();
  }

  function redraw() {
    ctx.clearRect(0, 0, SZ, SZ);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, SZ, SZ);
    drawGrid();
    strokes.forEach(paintStroke);
  }

  function tick() {
    ctr.textContent    = strokes.length ? L[2] + ': ' + strokes.length : '';
    undBtn.disabled    = !strokes.length;
    clrBtn.disabled    = !strokes.length;
  }

  function pt(e) {
    var r = cvs.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) * SZ / r.width,
      y: (e.clientY - r.top)  * SZ / r.height
    };
  }

  /* ── Pointer events (mouse + touch unified) ──────────────────────── */
  cvs.addEventListener('pointerdown', function (e) {
    e.preventDefault();
    cvs.setPointerCapture(e.pointerId);
    dn  = true;
    cur = [pt(e)];
  });

  cvs.addEventListener('pointermove', function (e) {
    if (!dn) { return; }
    e.preventDefault();
    cur.push(pt(e));
    redraw();
    paintStroke(cur);
  });

  function endStroke() {
    if (!dn) { return; }
    dn = false;
    if (cur.length > 1) { strokes.push(cur.slice()); }
    cur = [];
    redraw();
    tick();
  }

  cvs.addEventListener('pointerup',     endStroke);
  cvs.addEventListener('pointercancel', endStroke);

  redraw();
  tick();
}());"""


def build_block(cfg: dict) -> str:
    """Return the full HTML block to inject into a card template."""
    size = cfg.get("canvas_size", 300)
    grid = cfg.get("grid_type", "tian")
    sw   = cfg.get("stroke_width", 3)
    sc   = cfg.get("stroke_color", "#1a1a1a")
    gc   = cfg.get("grid_color", "#cccccc")
    bg   = cfg.get("background_color", "#ffffff")

    anchor = (
        f'<div id="kda-anchor" '
        f'data-size="{size}" data-grid="{grid}" '
        f'data-sw="{sw}" data-sc="{sc}" '
        f'data-gc="{gc}" data-bg="{bg}"></div>'
    )
    return (
        f"{MARKER_START}\n"
        f"{anchor}\n"
        f"<script>\n{_CANVAS_JS}\n</script>\n"
        f"{MARKER_END}"
    )


def inject(qfmt: str, cfg: dict) -> str:
    if MARKER_START in qfmt:
        return qfmt
    return qfmt + "\n" + build_block(cfg)


def remove(qfmt: str) -> str:
    pattern = re.compile(
        r"\n?" + re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    return pattern.sub("", qfmt)


def has_canvas(qfmt: str) -> bool:
    return MARKER_START in qfmt
