from __future__ import annotations

import re

MARKER_START = "<!-- KANJI-DRAW-START -->"
MARKER_END = "<!-- KANJI-DRAW-END -->"

_CANVAS_JS = r"""(function () {
  var a = document.getElementById('kda-anchor');
  if (!a || document.getElementById('kda-wrap')) { return; }

  var d   = a.dataset;
  var SZ  = parseInt(d.size, 10) || 300;
  var SW  = parseFloat(d.sw) || 3;
  var SC  = d.sc || '#1a1a1a';
  var GC  = d.gc || '#aaaaaa';
  var BG  = d.bg || '#ffffff';

  // Grid cycles: tian (田) → mi (米) → none, starting from injected default
  var GRIDS = ['tian', 'mi', 'none'];
  var GRID_ICONS = ['田', '米', '✕'];
  var gi = Math.max(0, GRIDS.indexOf(d.grid || 'tian'));

  var LABELS = {
    en: { clear: 'Clear', undo: 'Undo', strokes: 'Strokes' },
    es: { clear: 'Borrar', undo: 'Deshacer', strokes: 'Trazos' },
    ja: { clear: 'クリア', undo: '元に戻す', strokes: '画数' }
  };
  var lc = (navigator.language || 'en').slice(0, 2);
  var L  = LABELS[lc] || LABELS['en'];

  var strokes = [], cur = [], dn = false;

  /* ── Inject styles once so !important wins over Anki card themes ── */
  if (!document.getElementById('kda-style')) {
    var css = document.createElement('style');
    css.id = 'kda-style';
    css.textContent = [
      '#kda-wrap{margin:16px auto;-webkit-user-select:none;user-select:none}',
      '#kda-outer{width:min(100%,' + SZ + 'px);margin:0 auto}',
      /* aspect-ratio keeps the canvas square when CSS scales width */
      '#kda-canvas{display:block!important;width:100%!important;aspect-ratio:1/1!important;',
        'border:2px solid #888!important;border-radius:6px!important;',
        'cursor:crosshair!important;touch-action:none!important}',
      '#kda-bar{display:flex!important;justify-content:center!important;',
        'align-items:center!important;flex-wrap:wrap!important;',
        'gap:6px!important;margin-top:8px!important}',
      '#kda-wrap button{',
        'padding:5px 14px!important;font-size:14px!important;line-height:1.4!important;',
        'border-radius:4px!important;border:1px solid #999!important;',
        'background:#f0f0f0!important;color:#333!important;',
        'cursor:pointer!important;box-shadow:none!important}',
      '#kda-wrap button:disabled{opacity:.4!important;cursor:default!important}',
      '#kda-ctr{font-size:13px!important;color:#666!important;',
        'min-width:56px!important;display:inline-block!important}',
      /* Dark-mode overrides (Anki adds .night_mode or .nightMode on body) */
      '.night_mode #kda-canvas,.nightMode #kda-canvas{border-color:#555!important}',
      '.night_mode #kda-wrap button,.nightMode #kda-wrap button{',
        'background:#3a3a3a!important;color:#ddd!important;border-color:#666!important}',
      '.night_mode #kda-ctr,.nightMode #kda-ctr{color:#aaa!important}',
    ].join('');
    document.head.appendChild(css);
  }

  /* ── DOM ─────────────────────────────────────────────────────────── */
  var wrap  = document.createElement('div');  wrap.id  = 'kda-wrap';
  var outer = document.createElement('div');  outer.id = 'kda-outer';
  var cvs   = document.createElement('canvas'); cvs.id  = 'kda-canvas';
  var bar   = document.createElement('div');  bar.id   = 'kda-bar';

  cvs.width  = SZ;
  cvs.height = SZ;

  function mkBtn(label, fn) {
    var b = document.createElement('button');
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  }

  var clrBtn  = mkBtn(L.clear, function () { strokes = []; redraw(); tick(); });
  var undBtn  = mkBtn(L.undo,  function () {
    if (strokes.length) { strokes.pop(); redraw(); tick(); }
  });
  var gridBtn = mkBtn(GRID_ICONS[gi], function () {
    gi = (gi + 1) % GRIDS.length;
    gridBtn.textContent = GRID_ICONS[gi];
    redraw();
  });
  var ctr = document.createElement('span');
  ctr.id = 'kda-ctr';

  bar.appendChild(clrBtn);
  bar.appendChild(undBtn);
  bar.appendChild(gridBtn);
  bar.appendChild(ctr);
  outer.appendChild(cvs);
  wrap.appendChild(outer);
  wrap.appendChild(bar);
  a.insertAdjacentElement('afterend', wrap);

  /* ── Drawing ─────────────────────────────────────────────────────── */
  var ctx = cvs.getContext('2d');

  function drawGrid() {
    var g = GRIDS[gi];
    if (g === 'none') { return; }
    ctx.save();
    ctx.strokeStyle = GC;
    ctx.lineWidth   = 1;
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(SZ / 2, 0);   ctx.lineTo(SZ / 2, SZ); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, SZ / 2);   ctx.lineTo(SZ, SZ / 2); ctx.stroke();
    if (g === 'mi') {
      ctx.beginPath(); ctx.moveTo(4, 4);       ctx.lineTo(SZ - 4, SZ - 4); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(SZ - 4, 4);  ctx.lineTo(4, SZ - 4);      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  function paintStroke(pts) {
    if (pts.length < 2) { return; }
    ctx.save();
    ctx.strokeStyle = SC; ctx.lineWidth = SW;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
    for (var i = 1; i < pts.length; i++) { ctx.lineTo(pts[i].x, pts[i].y); }
    ctx.stroke(); ctx.restore();
  }

  function redraw() {
    ctx.clearRect(0, 0, SZ, SZ);
    ctx.fillStyle = BG; ctx.fillRect(0, 0, SZ, SZ);
    drawGrid(); strokes.forEach(paintStroke);
  }

  function tick() {
    ctr.textContent = strokes.length ? L.strokes + ': ' + strokes.length : '';
    undBtn.disabled = !strokes.length;
    clrBtn.disabled = !strokes.length;
  }

  function pt(e) {
    var r = cvs.getBoundingClientRect();
    return { x: (e.clientX - r.left) * SZ / r.width,
             y: (e.clientY - r.top)  * SZ / r.height };
  }

  /* ── Pointer events (mouse + touch unified) ──────────────────────── */
  cvs.addEventListener('pointerdown', function (e) {
    e.preventDefault(); cvs.setPointerCapture(e.pointerId); dn = true; cur = [pt(e)];
  });
  cvs.addEventListener('pointermove', function (e) {
    if (!dn) { return; } e.preventDefault(); cur.push(pt(e)); redraw(); paintStroke(cur);
  });
  function endStroke() {
    if (!dn) { return; } dn = false;
    if (cur.length > 1) { strokes.push(cur.slice()); }
    cur = []; redraw(); tick();
  }
  cvs.addEventListener('pointerup',     endStroke);
  cvs.addEventListener('pointercancel', endStroke);

  /* ── iOS WKWebView fix ───────────────────────────────────────────────
     WKWebView's native swipe-back gesture recognizer intercepts horizontal
     touches before pointer events can claim them. touch-action:none in CSS
     is not honoured by the back-swipe gesture recognizer. The only reliable
     fix is to add non-passive touch listeners that call preventDefault(),
     which signals to the OS that the web content owns these touches.
     Pointer events still fire normally after this — preventDefault() on a
     touch event only suppresses browser defaults (scroll, navigate), not the
     derived pointer event dispatch. ─────────────────────────────────── */
  /* ── Contain all input events inside the canvas ─────────────────────
     preventDefault() blocks browser defaults (scroll, navigate) but the
     event still bubbles. AnkiMobile's tap-to-flip recognizer lives higher
     in the tree, so we must also stopPropagation() on every touch/click
     that originates inside the canvas. ─────────────────────────────── */
  var _tp = { passive: false };
  function _eat(e) { e.preventDefault(); e.stopPropagation(); }
  cvs.addEventListener('touchstart',  _eat, _tp);
  cvs.addEventListener('touchmove',   _eat, _tp);
  cvs.addEventListener('touchend',    _eat, _tp);
  cvs.addEventListener('touchcancel', _eat, _tp);
  cvs.addEventListener('click',       _eat);

  redraw(); tick();
}());"""


def build_block(cfg: dict) -> str:
    """Return the full HTML block to inject into a card template."""
    size = cfg.get("canvas_size", 300)
    grid = cfg.get("grid_type", "tian")
    sw   = cfg.get("stroke_width", 3)
    sc   = cfg.get("stroke_color", "#1a1a1a")
    gc   = cfg.get("grid_color", "#aaaaaa")
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
