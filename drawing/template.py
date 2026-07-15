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

  // localStorage lets the user's preference survive across cards and sessions.
  // Falls back to the value baked in at injection time (from addon config).
  var _LS_KEY = 'kda_persist';
  var _lsVal;
  try { _lsVal = localStorage.getItem(_LS_KEY); } catch(e) { _lsVal = null; }
  var PERSIST = (_lsVal !== null) ? (_lsVal === '1') : (d.persist !== '0');

  // Same idea, for whether Undo / exiting-and-re-entering the deck restores
  // the front-side drawing as-is (true) or always starts it blank (false).
  var _LS_KEY_RESTORE = 'kda_restore_undo';
  var _lsRestoreVal;
  try { _lsRestoreVal = localStorage.getItem(_LS_KEY_RESTORE); } catch(e) { _lsRestoreVal = null; }
  var RESTORE = (_lsRestoreVal !== null) ? (_lsRestoreVal === '1') : (d.restore !== '0');

  // Language baked in at injection time from Anki's locale; falls back to
  // browser locale so cards synced to other devices still pick a language.
  var LABELS = {
    en: { clear: 'Clear', undo: 'Undo', strokes: 'Strokes', yourWriting: '✎ Your writing',
          keep: 'Keep', fresh: 'Fresh' },
    es: { clear: 'Borrar', undo: 'Deshacer', strokes: 'Trazos', yourWriting: '✎ Tu escritura',
          keep: 'Mantener', fresh: 'Nuevo' },
    ja: { clear: 'クリア', undo: '元に戻す', strokes: '画数', yourWriting: '✎ あなたの字',
          keep: '保持', fresh: '新規' }
  };
  var lc = d.lang || (navigator.language || 'en').slice(0, 2);
  var L  = LABELS[lc] || LABELS['en'];

  /* ── Card-identity fingerprint ────────────────────────────────────────
     AnkiMobile doesn't run this add-on's Python code at all, so there is
     no host-supplied card id available on every platform — this has to
     work from pure client-side signals alone. Hash the card's own
     rendered content (everything before our injected block) as a
     stand-in for "which card is this": the same card always renders the
     same content. ──────────────────────────────────────────────────── */
  function _fingerprint() {
    var src = document.body ? document.body.innerHTML : '';
    var idx = src.indexOf('id="kda-anchor"');
    if (idx !== -1) { src = src.slice(0, idx); }
    var h = 0;
    for (var i = 0; i < src.length; i++) { h = (h * 31 + src.charCodeAt(i)) | 0; }
    return String(h);
  }

  var _cid = _fingerprint();

  /* ── Two storage slots for two separate jobs ──────────────────────────
     _LAST_KEY: the immediate front→back handoff within a single flip.
     This is a direct, immediate sequence — no other card can appear in
     between a front and flipping to its OWN back — so a single shared
     slot is exactly as safe here as it always was; it doesn't need any
     fingerprint matching (using the fingerprint for this too used to
     intermittently break the handoff from the second card of a session
     onward, likely from some subtle difference between a card's content
     rendered standalone vs embedded into its own answer).
     _PERCARD_KEY: keyed by fingerprint, for restoring a card's drawing
     when its front is shown again after OTHER cards were shown in
     between (Undo after grading, or exiting/re-entering the deck) —
     exactly the case a single shared slot can't survive, since a
     different card's front would have overwritten it. ───────────────── */
  var _LAST_KEY    = 'kda_last_strokes';
  var _PERCARD_KEY = 'kda_strokes_' + _cid;

  // Small LRU so localStorage doesn't grow without bound over a long
  // review session — only the most recently shown cards keep their
  // per-card stored strokes around.
  var _RECENT_KEY = 'kda_recent';
  var _MAX_RECENT = 30;
  function _touchRecent(fp) {
    var recent = [];
    try { recent = JSON.parse(localStorage.getItem(_RECENT_KEY) || '[]'); } catch(e) {}
    var idx = recent.indexOf(fp);
    if (idx !== -1) { recent.splice(idx, 1); }
    recent.push(fp);
    while (recent.length > _MAX_RECENT) {
      var evicted = recent.shift();
      try { localStorage.removeItem('kda_strokes_' + evicted); } catch(e) {}
    }
    try { localStorage.setItem(_RECENT_KEY, JSON.stringify(recent)); } catch(e) {}
  }

  /* Per-card storage is stamped with a timestamp and expires after a
     short, configurable window: "Keep" is meant for short interruptions
     within the SAME review session (Undo after grading, exiting/
     re-entering the deck) — not for "Again" requeuing the card for
     another attempt later in the same session (Anki's shortest learning
     step is ~1 minute), and not for a previous day's drawing coming back
     when spaced repetition resurfaces the same card later. A plain
     content match can't tell any of these apart on its own, since the
     card's content is identical every time; localStorage has no
     built-in expiry either, so both are handled with this timestamp. */
  var _MAX_AGE_MS = (parseInt(d.keepWindow, 10) || 90) * 1000;
  function _readPerCard() {
    var raw;
    try { raw = JSON.parse(localStorage.getItem(_PERCARD_KEY) || 'null'); } catch(e) { raw = null; }
    if (!raw || typeof raw.t !== 'number' || (Date.now() - raw.t) > _MAX_AGE_MS) { return []; }
    return raw.s || [];
  }
  function _writePerCard(s) {
    try { localStorage.setItem(_PERCARD_KEY, JSON.stringify({ t: Date.now(), s: s })); } catch(e) {}
  }

  var strokes = [], cur = [], dn = false;

  /* ── Front vs. back detection ─────────────────────────────────────────
     A front/back flip-flop tracked in session storage can't tell "this
     is the back" apart from "the SAME front shown again" (undo, or
     exiting/re-entering the deck before flipping) — both look identical
     to a 2-state toggle. This uses a structural signal instead: Anki's
     own default answer template always has an hr with id "answer"
     between the embedded front side and the Back field — checking for it
     directly needs no session history. Custom templates that both drop
     the front-side embed AND remove that hr are the one case this can't
     detect; the canvas then just behaves like the front there.
     NOTE: never spell out Anki's double-brace field-reference syntax in
     this comment — Anki substitutes that pattern anywhere in the raw
     template text, comments included, before the browser ever sees this
     script. ──────────────────────────────────────────────────────────── */
  var IS_BACK = !!document.getElementById('answer');

  if (IS_BACK) {
    // Answer side of the same card — read back what the front (of this
    // same flip) just saved, regardless of any fingerprint matching.
    if (PERSIST) {
      try { strokes = JSON.parse(localStorage.getItem(_LAST_KEY) || '[]'); } catch(e) {}
    }
    // Lock is OFF → don't render anything on the back
    if (!PERSIST) { return; }
  } else {
    if (RESTORE) {
      // Whatever was last drawn for THIS exact card, if anything and if
      // recent enough — still there even if other cards were shown in
      // between (e.g. grading, then Undo bringing this one back).
      strokes = _readPerCard();
    } else {
      // The user prefers a fresh canvas whenever the front is shown,
      // including a genuinely new card, which never had anything stored.
      try { localStorage.removeItem(_PERCARD_KEY); } catch(e) {}
    }
    _touchRecent(_cid);
  }

  /* ── Inject styles once so !important wins over Anki card themes ── */
  if (!document.getElementById('kda-style')) {
    var css = document.createElement('style');
    css.id = 'kda-style';
    css.textContent = [
      /* touch-action:manipulation on the whole wrap prevents double-tap zoom
         everywhere inside it; canvas overrides to none for drawing. */
      '#kda-wrap{margin:16px auto;-webkit-user-select:none;user-select:none;',
        'touch-action:manipulation!important}',
      '#kda-outer{width:min(100%,' + SZ + 'px);margin:0 auto}',
      '#kda-canvas{display:block!important;width:100%!important;aspect-ratio:1/1!important;',
        'border:2px solid #888!important;border-radius:6px!important;cursor:crosshair!important;',
        /* none: disables ALL gestures (scroll, zoom, swipe) on the canvas */
        'touch-action:none!important;',
        /* suppress iOS long-press callout and text-selection highlight */
        '-webkit-touch-callout:none!important;-webkit-tap-highlight-color:transparent!important}',
      '#kda-bar{display:flex!important;justify-content:center!important;',
        'align-items:center!important;flex-wrap:wrap!important;',
        'gap:6px!important;margin-top:8px!important}',
      '#kda-wrap button{',
        'padding:5px 14px!important;font-size:14px!important;line-height:1.4!important;',
        'border-radius:4px!important;border:1px solid #999!important;',
        'background:#f0f0f0!important;color:#333!important;cursor:pointer!important;',
        'box-shadow:none!important;',
        /* manipulation: removes 300ms tap delay + double-tap zoom on buttons */
        'touch-action:manipulation!important;',
        /* no blue highlight flash on tap, no long-press callout */
        '-webkit-tap-highlight-color:transparent!important;-webkit-touch-callout:none!important}',
      '#kda-wrap button:disabled{opacity:.4!important;cursor:default!important}',
      /* Clear/Undo are the buttons used on every stroke — bigger tap target */
      '#kda-wrap button.kda-primary{',
        'padding:8px 20px!important;font-size:16px!important;font-weight:600!important}',
      /* Grid/lock/keep are set-once-and-forget — shrink them out of the way */
      '#kda-wrap button.kda-settings{',
        'padding:3px 9px!important;font-size:12px!important}',
      '#kda-sep{width:1px!important;align-self:stretch!important;margin:2px 2px!important;',
        'background:#ccc!important}',
      '.night_mode #kda-sep,.nightMode #kda-sep{background:#555!important}',
      '#kda-ctr{font-size:13px!important;color:#666!important;',
        'min-width:56px!important;display:inline-block!important}',
      /* Dark-mode overrides (Anki adds .night_mode or .nightMode on body) */
      '.night_mode #kda-canvas,.nightMode #kda-canvas{border-color:#555!important}',
      '.night_mode #kda-wrap button,.nightMode #kda-wrap button{',
        'background:#3a3a3a!important;color:#ddd!important;border-color:#666!important}',
      '.night_mode #kda-ctr,.nightMode #kda-ctr{color:#aaa!important}',
      '#kda-wrap button.kda-on{background:#d4edda!important;border-color:#5cb85c!important;color:#155724!important}',
      '.night_mode #kda-wrap button.kda-on,.nightMode #kda-wrap button.kda-on{',
        'background:#1e3a22!important;border-color:#5cb85c!important;color:#8fd49a!important}',
      /* Back-side compact mode inside <details> — never covers other content */
      '#kda-wrap.kda-back{margin:8px auto!important}',
      '#kda-wrap.kda-back #kda-outer{width:min(100%,' + Math.round(SZ * 0.5) + 'px)!important}',
      '#kda-wrap.kda-back #kda-canvas{pointer-events:none!important;cursor:default!important}',
      '#kda-wrap.kda-back #kda-bar{margin-top:4px!important}',
      '#kda-details{display:block!important;margin:12px 0 4px!important}',
      '#kda-summary{cursor:pointer!important;font-size:13px!important;color:#888!important;',
        '-webkit-user-select:none!important;user-select:none!important;list-style:none!important}',
      '#kda-summary::-webkit-details-marker{display:none!important}',
      '.night_mode #kda-summary,.nightMode #kda-summary{color:#aaa!important}',
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

  // Clear/Undo fire on every stroke, so they get the "primary" (bigger) style
  // and sit together, closest to the canvas. Grid/lock/keep are set-once
  // preferences, so they're smaller and separated by a divider.
  var clrBtn  = mkBtn(L.clear, function () { strokes = []; redraw(); tick(); });
  clrBtn.classList.add('kda-primary');
  var undBtn  = mkBtn(L.undo,  function () {
    if (strokes.length) { strokes.pop(); redraw(); tick(); }
  });
  undBtn.classList.add('kda-primary');
  var gridBtn = mkBtn(GRID_ICONS[gi], function () {
    gi = (gi + 1) % GRIDS.length;
    gridBtn.textContent = GRID_ICONS[gi];
    redraw();
  });
  gridBtn.classList.add('kda-settings');
  var keepBtn = mkBtn(PERSIST ? '🔒' : '🔓', function () {
    PERSIST = !PERSIST;
    try { localStorage.setItem(_LS_KEY, PERSIST ? '1' : '0'); } catch(e) {}
    keepBtn.textContent = PERSIST ? '🔒' : '🔓';
    keepBtn.classList.toggle('kda-on', PERSIST);
  });
  keepBtn.classList.add('kda-settings');
  keepBtn.classList.toggle('kda-on', PERSIST);
  keepBtn.title = 'Keep drawing on flip';

  var restBtn = mkBtn(RESTORE ? L.keep : L.fresh, function () {
    RESTORE = !RESTORE;
    try { localStorage.setItem(_LS_KEY_RESTORE, RESTORE ? '1' : '0'); } catch(e) {}
    restBtn.textContent = RESTORE ? L.keep : L.fresh;
    restBtn.classList.toggle('kda-on', RESTORE);
  });
  restBtn.classList.add('kda-settings');
  restBtn.classList.toggle('kda-on', RESTORE);
  restBtn.title = 'Keep drawing when this card’s front is shown again';

  var ctr = document.createElement('span');
  ctr.id = 'kda-ctr';

  var sep = document.createElement('span');
  sep.id = 'kda-sep';

  bar.appendChild(clrBtn);
  bar.appendChild(undBtn);
  bar.appendChild(ctr);
  bar.appendChild(sep);
  bar.appendChild(gridBtn);
  bar.appendChild(keepBtn);
  bar.appendChild(restBtn);
  outer.appendChild(cvs);
  wrap.appendChild(outer);
  wrap.appendChild(bar);

  if (IS_BACK) {
    wrap.classList.add('kda-back');
    // Hide editing controls — back is read-only compare view
    clrBtn.style.display  = 'none';
    undBtn.style.display  = 'none';
    gridBtn.style.display = 'none';
    keepBtn.style.display = 'none';
    restBtn.style.display = 'none';
    sep.style.display     = 'none';
    // Wrap in <details> so it never overlaps card content regardless of layout.
    // Opens automatically when there is something to compare.
    var det = document.createElement('details');
    det.id = 'kda-details';
    if (strokes.length > 0) { det.open = true; }
    var sum = document.createElement('summary');
    sum.id = 'kda-summary';
    det.appendChild(sum);
    det.appendChild(wrap);
    a.insertAdjacentElement('afterend', det);
  } else {
    a.insertAdjacentElement('afterend', wrap);
  }

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
    // Always saved (regardless of PERSIST/RESTORE) — those only gate
    // whether the back side or a later front redisplay are allowed to
    // read these back, not whether drawing itself gets recorded.
    // tick() only ever runs while drawing on the front (the back is
    // read-only), so both slots are only ever written from there.
    try { localStorage.setItem(_LAST_KEY, JSON.stringify(strokes)); } catch(e) {}
    _writePerCard(strokes);
    var sum = document.getElementById('kda-summary');
    if (sum) {
      sum.textContent = L.yourWriting + (strokes.length ? ' (' + strokes.length + ')' : '');
    }
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
  cvs.addEventListener('touchstart',   _eat, _tp);
  cvs.addEventListener('touchmove',    _eat, _tp);
  cvs.addEventListener('touchend',     _eat, _tp);
  cvs.addEventListener('touchcancel',  _eat, _tp);
  cvs.addEventListener('click',        _eat);
  // Prevent long-press context menu (Save Image / Copy) on the canvas
  cvs.addEventListener('contextmenu',  _eat);

  redraw(); tick();
}());"""


def build_block(cfg: dict) -> str:
    """Return the full HTML block to inject into a card template."""
    from .i18n import _detect_lang

    size    = cfg.get("canvas_size", 300)
    grid    = cfg.get("grid_type", "tian")
    sw      = cfg.get("stroke_width", 3)
    sc      = cfg.get("stroke_color", "#1a1a1a")
    gc      = cfg.get("grid_color", "#aaaaaa")
    bg      = cfg.get("background_color", "#ffffff")
    persist = "1" if cfg.get("persist_drawing", True) else "0"
    restore = "1" if cfg.get("restore_after_undo", True) else "0"
    keep_window = cfg.get("keep_window_seconds", 90)
    lang    = _detect_lang()

    anchor = (
        f'<div id="kda-anchor" '
        f'data-size="{size}" data-grid="{grid}" '
        f'data-sw="{sw}" data-sc="{sc}" '
        f'data-gc="{gc}" data-bg="{bg}" '
        f'data-persist="{persist}" data-restore="{restore}" '
        f'data-keep-window="{keep_window}" '
        f'data-lang="{lang}"></div>'
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
