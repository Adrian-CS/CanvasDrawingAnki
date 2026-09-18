from __future__ import annotations

import re
from html import escape, unescape

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
          keep: 'Keep', fresh: 'Fresh', check: 'Check',
          checkOn: 'Check strokes against the expected character',
          allRight: 'Correct — all {n} strokes',
          score: '{ok} of {n} strokes correct',
          missing: '{n} stroke(s) missing',
          extra: '{n} stroke(s) too many',
          eShape: 'stroke {i}: wrong shape',
          ePlace: 'stroke {i}: right shape, wrong place',
          eExtra: 'stroke {i}: extra stroke',
          eLen: 'stroke {i}: wrong length',
          eOrder: 'stroke {i}: out of order',
          eRev: 'stroke {i}: drawn backwards',
          okStroke: 'stroke {i} ✓',
          more: 'and {n} more',
          noData: 'Stroke data not found — see the add-on docs',
          noChar: 'No reference for {c}' },
    es: { clear: 'Borrar', undo: 'Deshacer', strokes: 'Trazos', yourWriting: '✎ Tu escritura',
          keep: 'Mantener', fresh: 'Nuevo', check: 'Comprobar',
          checkOn: 'Comprobar los trazos con el carácter esperado',
          allRight: '¡Correcto! Los {n} trazos',
          score: '{ok} de {n} trazos correctos',
          missing: 'Faltan {n} trazo(s)',
          extra: 'Sobran {n} trazo(s)',
          eShape: 'trazo {i}: forma incorrecta',
          ePlace: 'trazo {i}: forma correcta, sitio equivocado',
          eExtra: 'trazo {i}: trazo de más',
          eLen: 'trazo {i}: longitud incorrecta',
          eOrder: 'trazo {i}: fuera de orden',
          eRev: 'trazo {i}: dirección invertida',
          okStroke: 'trazo {i} ✓',
          more: 'y {n} más',
          noData: 'No se encontraron los datos de trazos — consulta la documentación',
          noChar: 'No hay referencia para {c}' },
    ja: { clear: 'クリア', undo: '元に戻す', strokes: '画数', yourWriting: '✎ あなたの字',
          keep: '保持', fresh: '新規', check: '判定',
          checkOn: '期待される文字と筆画を照合する',
          allRight: '正解 — 全{n}画',
          score: '{n}画中{ok}画が正しい',
          missing: '{n}画不足',
          extra: '{n}画多い',
          eShape: '{i}画目: 形が違います',
          ePlace: '{i}画目: 形は合っているが位置が違います',
          eExtra: '{i}画目: 余分な画',
          eLen: '{i}画目: 長さが違います',
          eOrder: '{i}画目: 筆順が違います',
          eRev: '{i}画目: 方向が逆です',
          okStroke: '{i}画目 ✓',
          more: 'ほか{n}件',
          noData: '筆画データが見つかりません — アドオンの説明を参照',
          noChar: '{c} の参照データがありません' }
  };
  var lc = d.lang || (navigator.language || 'en').slice(0, 2);
  var L  = LABELS[lc] || LABELS['en'];

  function fmt(tpl, vals) {
    return tpl.replace(/\{(\w+)\}/g, function (_, k) { return vals[k]; });
  }

  /* ── Stroke checking settings ─────────────────────────────────────────
     Same pattern as the other preferences: the add-on config bakes in a
     default at injection time, and a live toggle stored in localStorage
     overrides it per device. Checking additionally needs two things the
     toggle can't provide — a character to check against (from the field
     picked in the add-on dialog) and the reference data file in the
     collection's media folder — so it silently stays off without them. */
  var _LS_KEY_CHECK = 'kda_check';
  var _lsCheckVal;
  try { _lsCheckVal = localStorage.getItem(_LS_KEY_CHECK); } catch(e) { _lsCheckVal = null; }
  var CHECK = (_lsCheckVal !== null) ? (_lsCheckVal === '1') : (d.check === '1');
  // 'live' judges each stroke as it is finished; 'manual' waits for the
  // Check button so the whole character can be written undisturbed.
  var CHECK_MODE = d.checkMode === 'manual' ? 'manual' : 'live';
  // Multiplies every matching threshold — >1 is more forgiving.
  var TOL = parseFloat(d.tol) || 1;

  /* Where and how big this person writes, remembered between cards.
     Alignment is measured from the drawing's own bounding box, which needs
     a few strokes to exist — so without this the opening strokes of every
     character are judged against a full-em-box reference and anyone who
     writes smaller than the box is told their first two strokes are wrong.
     People write at a consistent size, so the last good measurement is a
     far better guess than assuming the box is filled. Stored as fractions
     of the canvas so it survives a change of canvas_size. */
  var _LS_KEY_FIT = 'kda_fit';
  function loadFit() {
    var f;
    try { f = JSON.parse(localStorage.getItem(_LS_KEY_FIT) || 'null'); } catch(e) { return null; }
    if (!f || typeof f.s !== 'number') { return null; }
    return { s: f.s, dx: f.dx * SZ, dy: f.dy * SZ };
  }
  function saveFit(xf) {
    try {
      localStorage.setItem(_LS_KEY_FIT, JSON.stringify(
        { s: xf.s, dx: xf.dx / SZ, dy: xf.dy / SZ }));
    } catch(e) {}
  }

  /* The characters to check against, rendered into a hidden span inside
     the anchor by the note field chosen in the dialog. A field often holds
     more than the one character — a whole word, or a word with its reading
     attached — so every CJK ideograph and kana in it gets its own canvas,
     in order. Furigana readings in square brackets are dropped first: in
     a field holding 漢字[かんじ] the reading is not something to write.
     The surrogate-pair branch covers characters above the BMP. */
  var CJK_RE = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]|[\ud840-\ud87f][\udc00-\udfff]/g;
  // A field holding a whole sentence would otherwise fill the card with
  // canvases; past this many, the rest are left out.
  var MAX_CELLS = 8;
  var _expEl  = document.getElementById('kda-expected');
  var _expTxt = _expEl ? (_expEl.textContent || '').replace(/\[[^\]]*\]/g, ' ') : '';
  var TARGETS = _expTxt.match(CJK_RE) || [];
  if (TARGETS.length > MAX_CELLS) { TARGETS = TARGETS.slice(0, MAX_CELLS); }
  // With nothing to check against there is still one canvas to draw on.
  var NCELLS = Math.max(1, TARGETS.length);

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

  /* Both slots hold one stroke list per canvas. Before multi-character
     cards they held a single canvas's strokes, and a drawing saved by that
     older version can still be sitting in localStorage when the add-on is
     updated mid-review — a stroke list starts with a point object, a list
     of canvases starts with an array, which tells the two apart. */
  function _normalize(raw) {
    if (!raw || !raw.length) { return []; }
    var first = raw[0];
    if (first && first.length && !Array.isArray(first[0])) { return [raw]; }
    return raw;
  }
  function _readPerCard() {
    var raw;
    try { raw = JSON.parse(localStorage.getItem(_PERCARD_KEY) || 'null'); } catch(e) { raw = null; }
    if (!raw || typeof raw.t !== 'number' || (Date.now() - raw.t) > _MAX_AGE_MS) { return []; }
    return _normalize(raw.s || []);
  }

  /* Always saved (regardless of PERSIST/RESTORE) — those only gate whether
     the back side or a later front redisplay are allowed to read these
     back, not whether drawing itself gets recorded. The back never writes:
     it would re-stamp the per-card timestamp and quietly extend the Keep
     window past the point the card was last drawn on. */
  function saveAll() {
    if (IS_BACK) { return; }
    var all = cells.map(function (c) { return c.strokes; });
    try { localStorage.setItem(_LAST_KEY, JSON.stringify(all)); } catch(e) {}
    try {
      localStorage.setItem(_PERCARD_KEY, JSON.stringify({ t: Date.now(), s: all }));
    } catch(e) {}
  }

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

  // One stroke list per canvas, in the order the canvases are built.
  var initial = [];

  if (IS_BACK) {
    // Answer side of the same card — read back what the front (of this
    // same flip) just saved, regardless of any fingerprint matching.
    if (PERSIST) {
      try {
        initial = _normalize(JSON.parse(localStorage.getItem(_LAST_KEY) || '[]'));
      } catch(e) {}
    }
    // Lock is OFF → don't render anything on the back
    if (!PERSIST) { return; }
  } else {
    if (RESTORE) {
      // Whatever was last drawn for THIS exact card, if anything and if
      // recent enough — still there even if other cards were shown in
      // between (e.g. grading, then Undo bringing this one back).
      initial = _readPerCard();
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
      /* The canvases sit in a row that wraps: one per character, each at
         most the configured size, sharing the width when there are
         several and falling onto the next line when they no longer fit. */
      '#kda-row{display:flex!important;flex-wrap:wrap!important;',
        'justify-content:center!important;align-items:flex-start!important;',
        'gap:10px!important}',
      '.kda-outer{flex-grow:0!important;flex-shrink:1!important;',
        'max-width:' + SZ + 'px!important;min-width:0}',
      '.kda-canvas{display:block!important;width:100%!important;aspect-ratio:1/1!important;',
        'border:2px solid #888!important;border-radius:6px!important;cursor:crosshair!important;',
        /* none: disables ALL gestures (scroll, zoom, swipe) on the canvas */
        'touch-action:none!important;',
        /* suppress iOS long-press callout and text-selection highlight */
        '-webkit-touch-callout:none!important;-webkit-tap-highlight-color:transparent!important}',
      '.kda-bar{display:flex!important;justify-content:center!important;',
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
      '#kda-settings-bar{margin-top:6px!important}',
      '#kda-sep{width:1px!important;align-self:stretch!important;margin:2px 2px!important;',
        'background:#ccc!important}',
      '.night_mode #kda-sep,.nightMode #kda-sep{background:#555!important}',
      '.kda-ctr{font-size:13px!important;color:#666!important;',
        'min-width:56px!important;display:inline-block!important}',
      /* Verdict line: its own row under the button bar so a long message
         never reflows the buttons. Hidden until there is something to say. */
      '.kda-msg{display:none;font-size:13px!important;line-height:1.5!important;',
        'text-align:center!important;margin-top:6px!important;padding:0 8px!important;',
        'color:#666!important}',
      '.kda-msg.kda-good{color:#2e7d32!important}',
      '.kda-msg.kda-bad{color:#c62828!important}',
      '.night_mode .kda-msg,.nightMode .kda-msg{color:#aaa!important}',
      '.night_mode .kda-msg.kda-good,.nightMode .kda-msg.kda-good{color:#8fd49a!important}',
      '.night_mode .kda-msg.kda-bad,.nightMode .kda-msg.kda-bad{color:#ef9a9a!important}',
      /* Dark-mode overrides (Anki adds .night_mode or .nightMode on body) */
      '.night_mode .kda-canvas,.nightMode .kda-canvas{border-color:#555!important}',
      '.night_mode #kda-wrap button,.nightMode #kda-wrap button{',
        'background:#3a3a3a!important;color:#ddd!important;border-color:#666!important}',
      '.night_mode .kda-ctr,.nightMode .kda-ctr{color:#aaa!important}',
      '#kda-wrap button.kda-on{background:#d4edda!important;border-color:#5cb85c!important;color:#155724!important}',
      '.night_mode #kda-wrap button.kda-on,.nightMode #kda-wrap button.kda-on{',
        'background:#1e3a22!important;border-color:#5cb85c!important;color:#8fd49a!important}',
      /* Back-side compact mode inside <details> — never covers other content */
      '#kda-wrap.kda-back{margin:8px auto!important}',
      '#kda-wrap.kda-back .kda-outer{max-width:' + Math.round(SZ * 0.5) + 'px!important}',
      '#kda-wrap.kda-back .kda-canvas{pointer-events:none!important;cursor:default!important}',
      '#kda-wrap.kda-back .kda-bar{margin-top:4px!important}',
      '#kda-details{display:block!important;margin:12px 0 4px!important}',
      '#kda-summary{cursor:pointer!important;font-size:13px!important;color:#888!important;',
        '-webkit-user-select:none!important;user-select:none!important;list-style:none!important}',
      '#kda-summary::-webkit-details-marker{display:none!important}',
      '.night_mode #kda-summary,.nightMode #kda-summary{color:#aaa!important}',
    ].join('');
    document.head.appendChild(css);
  }

  /* ══ Stroke checking ═══════════════════════════════════════════════════
     The reference data is KanjiVG's stroke paths, quantised to polylines
     and shipped as one media file (see drawing/data/README.md for the
     format). Everything below is pure client-side maths so it behaves the
     same on desktop and on mobile, where none of this add-on's Python
     runs at all. ─────────────────────────────────────────────────────── */

  var A64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  var A64I = {};
  for (var _k = 0; _k < A64.length; _k++) { A64I[A64.charAt(_k)] = _k; }

  /* Loads the reference data file on demand — only once a card actually
     has something to check. Anki re-runs this script per card, so the
     queue below collapses concurrent requests and, on desktop (where the
     page survives between cards), the parsed data is reused for the whole
     session; on mobile the webview serves it from its HTTP cache. */
  function withData(cb) {
    if (window.KDA_STROKE_DATA) { cb(true); return; }
    if (window.KDA_DATA_Q) { window.KDA_DATA_Q.push(cb); return; }
    var q = window.KDA_DATA_Q = [cb];
    var s = document.createElement('script');
    s.src = '_kda_strokes.js';
    function done() {
      var ok = !!window.KDA_STROKE_DATA;
      window.KDA_DATA_Q = null;
      q.forEach(function (f) { f(ok); });
    }
    s.addEventListener('load', done);
    s.addEventListener('error', done);
    document.head.appendChild(s);
  }

  /* Look one character up in the data blob. It is a plain newline-delimited
     string rather than an object so that loading it costs a string literal
     instead of building 6700 objects on every card render; the stroke
     payload is base64 characters only, so a CJK needle can never collide
     with one. */
  function refFor(ch) {
    var blob = window.KDA_STROKE_DATA || '';
    var at = blob.indexOf('\n' + ch + '|');
    if (at === -1) { return null; }
    var from = at + ch.length + 2;
    var to   = blob.indexOf('\n', from);
    return blob.slice(from, to === -1 ? blob.length : to).split(',').map(function (t) {
      var pts = [];
      for (var i = 0; i + 1 < t.length; i += 2) {
        pts.push({ x: A64I[t.charAt(i)]     / 63 * SZ,
                   y: A64I[t.charAt(i + 1)] / 63 * SZ });
      }
      return pts;
    });
  }

  // Points per stroke used for comparison. Both the drawn stroke and the
  // reference are resampled to this many evenly spaced points so they can
  // be compared position by position.
  var NRS = 16;

  function resample(pts, n) {
    if (pts.length < 2) {
      var only = pts[0] || { x: 0, y: 0 }, flat = [];
      while (flat.length < n) { flat.push(only); }
      return flat;
    }
    var seg = [], total = 0;
    for (var i = 1; i < pts.length; i++) {
      var dx = pts[i].x - pts[i - 1].x, dy = pts[i].y - pts[i - 1].y;
      var len = Math.sqrt(dx * dx + dy * dy);
      seg.push(len); total += len;
    }
    if (total === 0) { return resample([pts[0]], n); }
    var out = [pts[0]], step = total / (n - 1), walked = 0, si = 0, used = 0;
    for (var k = 1; k < n - 1; k++) {
      var want = k * step;
      while (si < seg.length - 1 && walked + seg[si] < want) { walked += seg[si]; si++; }
      used = seg[si] === 0 ? 0 : (want - walked) / seg[si];
      out.push({ x: pts[si].x + (pts[si + 1].x - pts[si].x) * used,
                 y: pts[si].y + (pts[si + 1].y - pts[si].y) * used });
    }
    out.push(pts[pts.length - 1]);
    return out;
  }

  function meanDist(a, b) {
    var sum = 0;
    for (var i = 0; i < a.length; i++) {
      var dx = a[i].x - b[i].x, dy = a[i].y - b[i].y;
      sum += Math.sqrt(dx * dx + dy * dy);
    }
    return sum / a.length;
  }

  function bbox(list) {
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    list.forEach(function (pts) {
      pts.forEach(function (p) {
        if (p.x < x0) { x0 = p.x; } if (p.x > x1) { x1 = p.x; }
        if (p.y < y0) { y0 = p.y; } if (p.y > y1) { y1 = p.y; }
      });
    });
    return { x0: x0, y0: y0, x1: x1, y1: y1, w: x1 - x0, h: y1 - y0 };
  }

  var IDENTITY = { s: 1, dx: 0, dy: 0 };

  /* People rarely fill the canvas the way a font fills its em box — most
     write smaller, and often off-centre. Comparing raw coordinates would
     then fail every stroke of an otherwise perfect character. So once
     enough strokes have been matched to say something about the writing's
     overall size and placement, fit a uniform scale + offset that maps the
     reference onto where the user is actually writing. Guard rails keep a
     wrong fit from rescuing a genuinely wrong character: at least three
     matched strokes, a span wide enough to be meaningful, and a scale that
     stays within sane bounds. */
  function fitTransform(drawnList, refList, minStrokes) {
    if (drawnList.length < (minStrokes || 3)) { return IDENTITY; }
    var db = bbox(drawnList), rb = bbox(refList);
    var span = Math.max(db.w, db.h), rspan = Math.max(rb.w, rb.h);
    if (span < SZ * 0.2 || rspan < SZ * 0.2) { return IDENTITY; }
    var s = span / rspan;
    if (s < 0.45 || s > 2.0) { return IDENTITY; }
    return { s: s,
             dx: (db.x0 + db.x1) / 2 - (rb.x0 + rb.x1) / 2 * s,
             dy: (db.y0 + db.y1) / 2 - (rb.y0 + rb.y1) / 2 * s };
  }

  function applyXf(pts, xf) {
    if (xf === IDENTITY) { return pts; }
    return pts.map(function (p) {
      return { x: p.x * xf.s + xf.dx, y: p.y * xf.s + xf.dy };
    });
  }

  /* The same stroke with its placement taken out, so its shape can be
     judged on its own — that is what separates "you drew the right stroke
     in the wrong place" from "that is not this stroke at all". */
  function centred(pts) {
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    pts.forEach(function (p) {
      if (p.x < x0) { x0 = p.x; } if (p.x > x1) { x1 = p.x; }
      if (p.y < y0) { y0 = p.y; } if (p.y > y1) { y1 = p.y; }
    });
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    return pts.map(function (p) { return { x: p.x - cx, y: p.y - cy }; });
  }

  function pathLength(pts) {
    var total = 0;
    for (var i = 1; i < pts.length; i++) {
      var dx = pts[i].x - pts[i - 1].x, dy = pts[i].y - pts[i - 1].y;
      total += Math.sqrt(dx * dx + dy * dy);
    }
    return total;
  }

  // Mean point distance, as a fraction of the canvas side, below which a
  // stroke counts as the reference stroke. Deliberately generous: this is
  // handwriting practice, not signature verification, and measurements on
  // deliberately sloppy writing (strokes misplaced by up to 7% of the
  // canvas, rotated by 5°, sheared) put it around here.
  var MATCH_TH = 0.075;
  /* Characters that differ only in how long one stroke is relative to
     another — 未/末, 土/士, 刀/力 — sit inside that distance, because
     averaging the difference over a whole stroke dilutes it. Comparing
     stroke lengths directly catches those without having to tighten the
     positional tolerance to where honest handwriting starts failing.
     Short strokes are exempt: a dot's length is mostly noise. */
  var LEN_RATIO = 1.5;
  var LEN_MIN = 0.08;
  // A stroke is only called "backwards" when reversing it fits clearly
  // better — for near-symmetric strokes both directions score alike and
  // calling those backwards would be noise.
  var REV_RATIO = 0.6;

  var VERDICT_COLORS = { bad: '#d9534f', order: '#e08e0b', rev: '#e08e0b' };
  // How many individual mistakes the verdict line spells out before it
  // just counts the rest.
  var MAX_ERRS = 3;

  /* Why a stroke matched nothing. Comparing it again with its placement
     taken out separates the three cases worth different advice: the shape
     is right and only sits in the wrong place, the shape is right but the
     stroke is far too long or short, or it is simply not that stroke.
     Without this everything that fails reads "wrong stroke", which tells
     the writer nothing they didn't already know. */
  function diagnose(drawn, refIdx, refs, xf, i, noFrame) {
    if (refIdx < 0) { return { v: 'bad', e: fmt(L.eExtra, { i: i + 1 }) }; }
    var refPts = applyXf(refs[refIdx], xf);
    var mine = resample(drawn, NRS), ref = resample(refPts, NRS);
    var lr = pathLength(refPts), ld = pathLength(drawn);
    var limit = MATCH_TH * TOL;

    // Same shape, just not where it belongs.
    var fwd = meanDist(centred(mine), centred(ref)) / SZ;
    var rev = meanDist(centred(mine.slice().reverse()), centred(ref)) / SZ;
    if (Math.min(fwd, rev) <= limit) {
      if (!noFrame && Math.max(lr, ld) / SZ > LEN_MIN &&
          (ld > lr * LEN_RATIO || lr > ld * LEN_RATIO)) {
        return { v: 'bad', e: fmt(L.eLen, { i: i + 1 }) };
      }
      if (rev < fwd * REV_RATIO) { return { v: 'rev', e: fmt(L.eRev, { i: i + 1 }) }; }
      return { v: 'bad', e: fmt(L.ePlace, { i: i + 1 }) };
    }

    // Same shape once the size is taken out too: the stroke runs the right
    // way, it is simply far too long or too short.
    if (!noFrame && ld > 0 && lr > 0) {
      var scaled = centred(mine).map(function (p) {
        return { x: p.x * lr / ld, y: p.y * lr / ld };
      });
      if (meanDist(scaled, centred(ref)) / SZ <= limit) {
        return { v: 'bad', e: fmt(L.eLen, { i: i + 1 }) };
      }
    }
    return { v: 'bad', e: fmt(L.eShape, { i: i + 1 }) };
  }

  /* Greedy sequential matching. Each drawn stroke is matched against the
     best still-unclaimed reference stroke; comparing against the expected
     one alone could not tell "wrong stroke" apart from "right stroke, drawn
     too early", which is exactly the mistake stroke-order practice is for.
     A stroke that matches nothing consumes the expected slot anyway so the
     rest of the character still lines up. */
  function evaluate(drawnList, refs, seed, noFrame) {
    var used = [], pairsD = [], pairsR = [], v = [], errs = [], refOf = [];
    var cost = 0, limit = MATCH_TH * TOL;
    for (var i = 0; i < drawnList.length; i++) {
      // A seed measured from the drawing as a whole beats anything derived
      // from matches made so far, which would need the very alignment they
      // are supposed to produce; without one, grow the fit from confirmed
      // matches as they accumulate.
      var xf = seed || fitTransform(pairsD, pairsR);
      var expected = -1, best = null;
      for (var j = 0; j < refs.length; j++) {
        if (used[j]) { continue; }
        if (expected === -1) { expected = j; }
        var refPts = applyXf(refs[j], xf);
        var ref = resample(refPts, NRS);
        var mine = resample(drawnList[i], NRS);
        var fwd = meanDist(mine, ref) / SZ;
        var rev = meanDist(mine.slice().reverse(), ref) / SZ;
        /* Before anything has been drawn to measure — the opening strokes
           of the first character this device ever checks — there is no way
           to know where on the canvas this person writes or how big.
           Judging placement then only punishes writing smaller than the em
           box, so fall back to comparing the shape alone until there is a
           frame to judge placement against. */
        if (noFrame) {
          fwd = Math.min(fwd, meanDist(centred(mine), centred(ref)) / SZ);
          rev = Math.min(rev, meanDist(centred(mine.slice().reverse()),
                                       centred(ref)) / SZ);
        }
        var score = Math.min(fwd, rev);
        // Only once there is a frame: against an unaligned reference every
        // stroke of someone writing at two thirds of the box is "too short".
        var lr = pathLength(refPts) / SZ, ld = pathLength(drawnList[i]) / SZ;
        var badLen = !noFrame && Math.max(lr, ld) > LEN_MIN &&
                     (ld > lr * LEN_RATIO || lr > ld * LEN_RATIO);
        if (!best || score < best.score) {
          best = { j: j, score: score, rev: rev < fwd * REV_RATIO,
                   badLen: badLen };
        }
      }
      if (!best || best.score > MATCH_TH * TOL) {
        // Nothing this could be. Consume the slot it should have filled so
        // the strokes after it are still judged against the right shapes.
        var why = diagnose(drawnList[i], expected, refs, xf, i, noFrame);
        v.push(why.v);
        errs.push(why.e);
        refOf.push(expected);
        cost += limit;
        if (expected !== -1) { used[expected] = true; }
        continue;
      }
      cost += best.score;
      // From here the stroke is at least *this* reference stroke, so pair
      // them up whatever the verdict — a wrong-length or reversed stroke
      // still tells the alignment where the writer is working, and letting
      // it fall through to the branch above would push every stroke after
      // it onto the wrong reference.
      used[best.j] = true;
      refOf.push(best.j);
      pairsD.push(drawnList[i]);
      pairsR.push(refs[best.j]);
      if (best.badLen) {
        v.push('bad');
        errs.push(fmt(L.eLen, { i: i + 1 }));
      } else if (best.j !== expected) {
        v.push('order');
        errs.push(fmt(L.eOrder, { i: i + 1 }));
      } else if (best.rev) {
        v.push('rev');
        errs.push(fmt(L.eRev, { i: i + 1 }));
      } else {
        v.push('ok');
      }
    }
    var xfFinal = fitTransform(pairsD, pairsR);
    return { v: v, errs: errs, xf: xfFinal, refOf: refOf, cost: cost,
             ok: v.filter(function (x) { return x === 'ok'; }).length };
  }

  function summarize(r, refs, drawnCount) {
    var parts = [];
    // Nothing written at all — say only that, without a 0-of-N tally.
    if (!drawnCount) {
      return { text: fmt(L.missing, { n: refs.length }), good: false };
    }
    if (drawnCount < refs.length) {
      parts.push(fmt(L.missing, { n: refs.length - drawnCount }));
    } else if (drawnCount > refs.length) {
      parts.push(fmt(L.extra, { n: drawnCount - refs.length }));
    }
    if (!parts.length && r.ok === refs.length) {
      return { text: fmt(L.allRight, { n: refs.length }), good: true };
    }
    parts.push(fmt(L.score, { ok: r.ok, n: refs.length }));
    // A badly missed 29-stroke kanji would otherwise produce a paragraph.
    // The first few mistakes are the ones worth fixing anyway, and the
    // strokes themselves stay marked on the canvas.
    var shown = r.errs.slice(0, MAX_ERRS);
    if (r.errs.length > MAX_ERRS) {
      shown.push(fmt(L.more, { n: r.errs.length - MAX_ERRS }));
    }
    return { text: parts.concat(shown).join(' · '), good: false };
  }

  /* ── DOM ─────────────────────────────────────────────────────────── */
  var wrap = document.createElement('div');  wrap.id = 'kda-wrap';
  var row  = document.createElement('div');  row.id  = 'kda-row';

  function mkBtn(label, fn) {
    var b = document.createElement('button');
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  }

  /* ── One cell per character ───────────────────────────────────────────
     A card whose field holds a whole word gets one canvas per character,
     each checked against its own reference. Everything that belongs to a
     single character — its canvas, strokes, verdicts, Clear/Undo and
     verdict line — lives in here; everything shared (the grid, the
     preference toggles, storage) stays outside, so the settings bar is
     not repeated N times. With one character this builds exactly the
     single canvas the add-on has always had. ─────────────────────────── */
  function makeCell(index, target, initialStrokes) {
    var cell = {
      index: index, target: target || '',
      strokes: initialStrokes || [], verdicts: [], ghosts: [],
      refs: null, checked: false,
    };
    var cur = [], dn = false;

    var outer = document.createElement('div');
    outer.className = 'kda-outer';
    outer.id = 'kda-outer-' + index;
    /* Every canvas gets the same width, so a character that wraps onto a
       second line is not suddenly drawn twice the size of its neighbours —
       which is what flex-grow does to a lone item on the last row. The
       width is set here rather than in the stylesheet because that is
       injected once and then shared by every card of the session, while
       the number of characters is per card.
       The second assignment stops them shrinking below a size you can
       write in, wrapping instead; a WebView too old for CSS max() simply
       drops it and keeps the plain share. */
    var share = NCELLS === 1 ? '100%'
      : 'calc((100% - ' + ((NCELLS - 1) * 10) + 'px) / ' + NCELLS + ')';
    outer.style.flexBasis = share;
    outer.style.flexBasis = 'max(150px,' + share + ')';
    var cvs = document.createElement('canvas');
    cvs.className = 'kda-canvas';
    cvs.id = 'kda-canvas-' + index;
    cvs.width = SZ;
    cvs.height = SZ;
    var bar = document.createElement('div');
    bar.className = 'kda-bar';
    bar.id = 'kda-bar-' + index;
    var ctr = document.createElement('span');
    ctr.className = 'kda-ctr';
    ctr.id = 'kda-ctr-' + index;
    var msg = document.createElement('div');
    msg.className = 'kda-msg';
    msg.id = 'kda-msg-' + index;

    var ctx = cvs.getContext('2d');

    /* Clear/Undo fire on every stroke, so they get the "primary" (bigger)
       style and sit closest to the canvas they belong to. Once there are
       several canvases sharing the width, the big version no longer fits
       under one on a phone and wraps onto two lines, so they shrink. */
    var btnSize = NCELLS === 1 ? 'kda-primary' : 'kda-settings';
    var clrBtn = mkBtn(L.clear, function () {
      cell.strokes = []; cell.verdicts = []; cell.ghosts = [];
      cell.checked = false;
      say(''); redraw(); tick();
    });
    clrBtn.classList.add(btnSize);
    var undBtn = mkBtn(L.undo, function () {
      if (!cell.strokes.length) { return; }
      cell.strokes.pop(); cell.verdicts.pop(); cell.ghosts = [];
      redraw(); tick();
    });
    undBtn.classList.add(btnSize);

    bar.appendChild(clrBtn);
    bar.appendChild(undBtn);
    bar.appendChild(ctr);
    outer.appendChild(cvs);
    outer.appendChild(bar);
    outer.appendChild(msg);
    row.appendChild(outer);

    /* ── Drawing ───────────────────────────────────────────────────── */
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

    function paintStroke(pts, color) {
      if (pts.length < 2) { return; }
      ctx.save();
      ctx.strokeStyle = color || SC; ctx.lineWidth = SW;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
      for (var i = 1; i < pts.length; i++) { ctx.lineTo(pts[i].x, pts[i].y); }
      ctx.stroke(); ctx.restore();
    }

    function paintGhost(pts) {
      if (pts.length < 2) { return; }
      ctx.save();
      ctx.strokeStyle = '#e08e0b'; ctx.globalAlpha = 0.5;
      ctx.lineWidth = SW; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.setLineDash([6, 5]);
      ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
      for (var i = 1; i < pts.length; i++) { ctx.lineTo(pts[i].x, pts[i].y); }
      ctx.stroke(); ctx.restore();
    }

    function redraw() {
      ctx.clearRect(0, 0, SZ, SZ);
      ctx.fillStyle = BG; ctx.fillRect(0, 0, SZ, SZ);
      drawGrid();
      cell.ghosts.forEach(paintGhost);
      cell.strokes.forEach(function (pts, i) {
        paintStroke(pts, VERDICT_COLORS[cell.verdicts[i]] || SC);
      });
    }

    function tick() {
      ctr.textContent = cell.strokes.length
        ? L.strokes + ': ' + cell.strokes.length : '';
      undBtn.disabled = !cell.strokes.length;
      clrBtn.disabled = !cell.strokes.length;
      saveAll();
      refreshSummary();
    }

    function say(text, good) {
      msg.textContent = text;
      msg.style.display = text ? 'block' : 'none';
      msg.classList.toggle('kda-good', !!good && !!text);
      msg.classList.toggle('kda-bad', !good && !!text);
    }

    /* ── Checking ──────────────────────────────────────────────────── */

    // Pulls this cell's reference in (loading the shared data file the
    // first time) and then runs `after`.
    function withRefs(after) {
      if (cell.refs) { after(true); return; }
      if (!cell.target) { after(false); return; }
      withData(function (ok) {
        if (!ok) { say(L.noData, false); after(false); return; }
        cell.refs = refFor(cell.target);
        if (!cell.refs) {
          say(fmt(L.noChar, { c: cell.target }), false); after(false); return;
        }
        after(true);
      });
    }

    /* Runs a full pass over everything drawn in this cell. Re-running from
       scratch on every stroke (rather than judging only the newest one)
       keeps live and on-demand checking in exact agreement, and lets an
       earlier verdict be revised once later strokes reveal how big the
       writing really is. `full` asks for the whole-character summary; live
       checking only reports the newest stroke until the character is
       complete. */
    function runCheck(full) {
      var refs = cell.refs;
      // An empty canvas has nothing to judge stroke by stroke, but asked
      // for the full verdict it is an answer in itself: the character was
      // not written.
      if (!refs || (!cell.strokes.length && !full)) { return; }
      // Measure how big and where the writing is before judging any of it:
      // the reference prefix of the same length is what a writer who is on
      // track has produced, so their bounding boxes should coincide.
      /* Which frame is this person writing in? Rather than guess once,
         try the candidates and keep whichever explains the drawing best:
         the em box itself, the size and position measured from the last
         character they completed, and the box of what they have drawn so
         far. Guessing once is what made a single badly misplaced stroke
         drag the measured box with it and mark the correct stroke beside
         it wrong too — that guess now simply loses to a better one. */
      var frames = [null];
      var learned = loadFit();
      if (learned) { frames.push(learned); }
      /* Two strokes are normally too few to measure a box from — one badly
         misplaced stroke would drag it along and make the correct stroke
         beside it look wrong too. A finished character is different: all of
         it is there to measure, and two-stroke characters like 刀 and 力
         would otherwise never get a frame at all and so never be told
         apart. */
      var complete = cell.strokes.length >= refs.length;
      var measured = fitTransform(
        cell.strokes, refs.slice(0, Math.min(cell.strokes.length, refs.length)),
        complete ? 2 : 3);
      if (measured !== IDENTITY) { frames.push(measured); }

      /* No frame, and not enough drawing to measure one: the opening
         strokes of the first character this device ever checks. Judge the
         shapes alone rather than punish writing smaller than the box.
         A finished character is never in that position — if its box came
         out implausible, that is the drawing being wrong, not the frame
         being unknown, and it is judged against the box itself. */
      var noFrame = frames.length === 1 && !complete;
      var r = null;
      frames.forEach(function (f) {
        var t = evaluate(cell.strokes, refs, f, noFrame);
        if (!r || t.cost < r.cost) { r = t; }
      });
      // Refit on the strokes that paired up, which drops any stroke that
      // was never going to match out of the measurement.
      if (!noFrame && r.xf !== IDENTITY) {
        var refined = evaluate(cell.strokes, refs, r.xf, false);
        if (refined.cost <= r.cost) { r = refined; }
      }

      cell.verdicts = r.v;
      // A measurement worth keeping: enough strokes landed for the fit to
      // mean something, so the next character's opening strokes start from
      // it instead of from an assumption.
      if (r.xf !== IDENTITY && r.ok >= 3) { saveFit(r.xf); }
      // Every stroke that went wrong shows where it should have gone —
      // being told a stroke is wrong without being shown the right one
      // leaves you nothing to correct towards. They appear only after the
      // stroke is already committed, so this is feedback, not tracing.
      cell.ghosts = [];
      for (var i = 0; i < r.v.length; i++) {
        var ri = r.refOf[i];
        if (r.v[i] !== 'ok' && ri >= 0) {
          cell.ghosts.push(applyXf(refs[ri], r.xf));
        }
      }
      cell.checked = true;
      redraw();
      if (full || cell.strokes.length >= refs.length) {
        var s = summarize(r, refs, cell.strokes.length);
        say(s.text, s.good);
      } else {
        var last = r.v[r.v.length - 1];
        say(last === 'ok' ? fmt(L.okStroke, { i: r.v.length })
                          : r.errs[r.errs.length - 1], last === 'ok');
      }
    }

    function clearVerdict() {
      cell.verdicts = []; cell.ghosts = []; cell.checked = false;
      say(''); redraw();
    }

    // Called when a stroke is finished. In live mode this judges the
    // stroke right away; in manual mode it only drops an already-shown
    // verdict, so drawing after checking doesn't leave a stale message.
    function afterStroke() {
      if (!CHECK || !cell.target) { return; }
      if (CHECK_MODE === 'live') {
        withRefs(function (ok) { if (ok) { runCheck(false); } });
      } else if (cell.checked) {
        clearVerdict();
      }
    }

    /* ── Pointer events (mouse + touch unified) ────────────────────── */
    function pt(e) {
      var r = cvs.getBoundingClientRect();
      return { x: (e.clientX - r.left) * SZ / r.width,
               y: (e.clientY - r.top)  * SZ / r.height };
    }

    cvs.addEventListener('pointerdown', function (e) {
      e.preventDefault(); cvs.setPointerCapture(e.pointerId); dn = true; cur = [pt(e)];
    });
    cvs.addEventListener('pointermove', function (e) {
      if (!dn) { return; } e.preventDefault(); cur.push(pt(e)); redraw(); paintStroke(cur);
    });
    function endStroke() {
      if (!dn) { return; } dn = false;
      if (cur.length > 1) { cell.strokes.push(cur.slice()); }
      cur = []; redraw(); tick(); afterStroke();
    }
    cvs.addEventListener('pointerup',     endStroke);
    cvs.addEventListener('pointercancel', endStroke);

    /* ── iOS WKWebView fix ─────────────────────────────────────────────
       WKWebView's native swipe-back gesture recognizer intercepts
       horizontal touches before pointer events can claim them.
       touch-action:none in CSS is not honoured by the back-swipe gesture
       recognizer. The only reliable fix is to add non-passive touch
       listeners that call preventDefault(), which signals to the OS that
       the web content owns these touches. Pointer events still fire
       normally after this — preventDefault() on a touch event only
       suppresses browser defaults (scroll, navigate), not the derived
       pointer event dispatch.
       preventDefault() blocks those defaults but the event still bubbles,
       and AnkiMobile's tap-to-flip recognizer lives higher in the tree, so
       every touch/click starting inside the canvas is stopped there
       too. ────────────────────────────────────────────────────────────── */
    var _tp = { passive: false };
    function _eat(e) { e.preventDefault(); e.stopPropagation(); }
    cvs.addEventListener('touchstart',   _eat, _tp);
    cvs.addEventListener('touchmove',    _eat, _tp);
    cvs.addEventListener('touchend',     _eat, _tp);
    cvs.addEventListener('touchcancel',  _eat, _tp);
    cvs.addEventListener('click',        _eat);
    // Prevent long-press context menu (Save Image / Copy) on the canvas
    cvs.addEventListener('contextmenu',  _eat);

    cell.bar = bar;
    cell.redraw = redraw;
    cell.tick = tick;
    cell.say = say;
    cell.withRefs = withRefs;
    cell.runCheck = runCheck;
    cell.clearVerdict = clearVerdict;
    cell.hideEditing = function () {
      clrBtn.style.display = 'none';
      undBtn.style.display = 'none';
    };
    return cell;
  }

  var cells = [];
  for (var ci = 0; ci < NCELLS; ci++) {
    cells.push(makeCell(ci, TARGETS[ci] || '', initial[ci] || []));
  }

  function eachCell(fn) { cells.forEach(fn); }

  function refreshSummary() {
    var sum = document.getElementById('kda-summary');
    if (!sum) { return; }
    var total = 0;
    eachCell(function (c) { total += c.strokes.length; });
    sum.textContent = L.yourWriting + (total ? ' (' + total + ')' : '');
  }

  /* ── Shared settings controls ─────────────────────────────────────── */
  var gridBtn = mkBtn(GRID_ICONS[gi], function () {
    gi = (gi + 1) % GRIDS.length;
    gridBtn.textContent = GRID_ICONS[gi];
    eachCell(function (c) { c.redraw(); });
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

  /* Checking has two controls: a settings-sized on/off toggle, and — in
     manual mode only — a primary Check button next to Clear/Undo. Both
     stay out of the way entirely on templates with no character to check
     against, so nothing new appears for people who don't use this. */
  var chkBtn = mkBtn('✓', function () {
    CHECK = !CHECK;
    try { localStorage.setItem(_LS_KEY_CHECK, CHECK ? '1' : '0'); } catch(e) {}
    chkBtn.classList.toggle('kda-on', CHECK);
    syncCheckUI();
    if (CHECK) {
      checkAll(CHECK_MODE === 'manual', true);
    } else {
      eachCell(function (c) { c.clearVerdict(); });
    }
  });
  chkBtn.classList.add('kda-settings');
  chkBtn.classList.toggle('kda-on', CHECK);
  chkBtn.title = L.checkOn;

  var goBtn = mkBtn(L.check, function () { checkAll(true, false); });
  goBtn.classList.add('kda-primary');

  var sep = document.createElement('span');
  sep.id = 'kda-sep';

  function syncCheckUI() {
    var show = CHECK && CHECK_MODE === 'manual' && TARGETS.length > 0;
    goBtn.style.display = show ? '' : 'none';
  }

  /* Judges every cell. `auto` marks the passes nobody asked for — opening a
     card, turning checking back on — which stay silent on a card with
     nothing drawn on it yet. Once something has been written, though, a
     character left blank is part of the answer and gets reported as
     missing rather than passed over. */
  function checkAll(full, auto) {
    if (!CHECK) { return; }
    var anyStrokes = false;
    eachCell(function (c) { if (c.strokes.length) { anyStrokes = true; } });
    if (auto && !anyStrokes) { return; }
    eachCell(function (c) {
      if (!c.target) { return; }
      c.withRefs(function (ok) { if (ok) { c.runCheck(full); } });
    });
  }

  /* With a single character the settings sit on the same row as Clear and
     Undo, exactly as they always have. With several, repeating them under
     every canvas would be noise, so they move to one shared row below. */
  var settingsBar = cells.length === 1 ? cells[0].bar
                                       : document.createElement('div');
  if (cells.length > 1) {
    settingsBar.id = 'kda-settings-bar';
    settingsBar.className = 'kda-bar';
  }
  settingsBar.appendChild(goBtn);
  // The divider separates Clear/Undo from the preference buttons; in a row
  // of its own there is nothing on its left to divide it from.
  if (cells.length === 1) { settingsBar.appendChild(sep); }
  settingsBar.appendChild(gridBtn);
  settingsBar.appendChild(keepBtn);
  settingsBar.appendChild(restBtn);
  settingsBar.appendChild(chkBtn);
  if (!TARGETS.length) { chkBtn.style.display = 'none'; }
  syncCheckUI();

  wrap.appendChild(row);
  if (cells.length > 1) { wrap.appendChild(settingsBar); }

  if (IS_BACK) {
    wrap.classList.add('kda-back');
    // Hide editing controls — back is read-only compare view
    eachCell(function (c) { c.hideEditing(); });
    goBtn.style.display   = 'none';
    gridBtn.style.display = 'none';
    keepBtn.style.display = 'none';
    restBtn.style.display = 'none';
    chkBtn.style.display  = 'none';
    sep.style.display     = 'none';
    // Wrap in <details> so it never overlaps card content regardless of
    // layout. Opens automatically when there is something to compare.
    var det = document.createElement('details');
    det.id = 'kda-details';
    var anyStrokes = false;
    eachCell(function (c) { if (c.strokes.length) { anyStrokes = true; } });
    if (anyStrokes) { det.open = true; }
    var sum = document.createElement('summary');
    sum.id = 'kda-summary';
    det.appendChild(sum);
    det.appendChild(wrap);
    a.insertAdjacentElement('afterend', det);
  } else {
    a.insertAdjacentElement('afterend', wrap);
  }

  eachCell(function (c) { c.redraw(); c.tick(); });
  refreshSummary();

  // A restored front drawing, or the back side showing what was written on
  // the front, both arrive with strokes already in place — judge them right
  // away instead of waiting for the next stroke that may never come. The
  // back always gets the full verdict since it is the compare view.
  checkAll(IS_BACK || CHECK_MODE === 'manual', true);
}());"""


def build_block(cfg: dict, expected_field: str | None = None) -> str:
    """Return the full HTML block to inject into a card template.

    ``expected_field`` names the note field holding the character the
    drawing should be checked against; without it the block still works,
    it just never offers stroke checking.
    """
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
    check   = "1" if cfg.get("check_strokes", False) else "0"
    mode    = "manual" if cfg.get("check_mode") == "manual" else "live"
    tol     = cfg.get("check_tolerance", 1.0)
    lang    = _detect_lang()

    # The expected character rides along as the field's rendered text rather
    # than as an attribute value: fields can contain quotes and markup, and
    # a text node needs no escaping to survive either. Anki substitutes the
    # field reference when the card is rendered, so this works unchanged on
    # mobile, where none of this add-on's Python code runs.
    expected = ""
    if expected_field:
        expected = (
            f'<span id="kda-expected" style="display:none">'
            f"{{{{text:{expected_field}}}}}</span>"
        )

    anchor = (
        f'<div id="kda-anchor" '
        f'data-size="{size}" data-grid="{grid}" '
        f'data-sw="{sw}" data-sc="{sc}" '
        f'data-gc="{gc}" data-bg="{bg}" '
        f'data-persist="{persist}" data-restore="{restore}" '
        f'data-keep-window="{keep_window}" '
        f'data-check="{check}" data-check-mode="{mode}" '
        f'data-tol="{tol}" '
        f'data-expected-field="{escape(expected_field or "", quote=True)}" '
        f'data-lang="{lang}">{expected}</div>'
    )
    return (
        f"{MARKER_START}\n"
        f"{anchor}\n"
        f"<script>\n{_CANVAS_JS}\n</script>\n"
        f"{MARKER_END}"
    )


def inject(qfmt: str, cfg: dict, expected_field: str | None = None) -> str:
    if MARKER_START in qfmt:
        return qfmt
    return qfmt + "\n" + build_block(cfg, expected_field)


def remove(qfmt: str) -> str:
    pattern = re.compile(
        r"\n?" + re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    return pattern.sub("", qfmt)


def has_canvas(qfmt: str) -> bool:
    return MARKER_START in qfmt


_FIELD_RE = re.compile(r'data-expected-field="([^"]*)"')


def expected_field(qfmt: str) -> str:
    """Return the field an already-injected block checks against, if any."""
    if not has_canvas(qfmt):
        return ""
    m = _FIELD_RE.search(qfmt)
    return unescape(m.group(1)) if m else ""
