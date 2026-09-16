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
          eBad: 'stroke {i}: wrong stroke',
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
          eBad: 'trazo {i}: incorrecto',
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
          eBad: '{i}画目: 誤り',
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

  /* The character to check against, rendered into a hidden span inside the
     anchor by the note field chosen in the dialog. Fields often hold more
     than the character alone (readings, a whole word, stray markup), so
     take the first CJK ideograph or kana found; the surrogate-pair branch
     covers the rarer characters above the BMP. */
  var CJK_RE = /[぀-ヿ㐀-䶿一-鿿豈-﫿]|[\ud840-\ud87f][\udc00-\udfff]/;
  var _expEl  = document.getElementById('kda-expected');
  var _expHit = _expEl ? (_expEl.textContent || '').match(CJK_RE) : null;
  var TARGET  = _expHit ? _expHit[0] : '';

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
      /* Verdict line: its own row under the button bar so a long message
         never reflows the buttons. Hidden until there is something to say. */
      '#kda-msg{display:none;font-size:13px!important;line-height:1.5!important;',
        'text-align:center!important;margin-top:6px!important;padding:0 8px!important;',
        'color:#666!important}',
      '#kda-msg.kda-good{color:#2e7d32!important}',
      '#kda-msg.kda-bad{color:#c62828!important}',
      '.night_mode #kda-msg,.nightMode #kda-msg{color:#aaa!important}',
      '.night_mode #kda-msg.kda-good,.nightMode #kda-msg.kda-good{color:#8fd49a!important}',
      '.night_mode #kda-msg.kda-bad,.nightMode #kda-msg.kda-bad{color:#ef9a9a!important}',
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
  var clrBtn  = mkBtn(L.clear, function () {
    strokes = []; verdicts = []; ghosts = []; CHECKED = false;
    say(''); redraw(); tick();
  });
  clrBtn.classList.add('kda-primary');
  var undBtn  = mkBtn(L.undo,  function () {
    if (!strokes.length) { return; }
    strokes.pop(); verdicts.pop(); ghosts = [];
    redraw(); tick();
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
      withRefs(function (ok) { if (ok && strokes.length) { runCheck(CHECK_MODE === 'manual'); } });
    } else {
      verdicts = []; ghosts = []; CHECKED = false; say(''); redraw();
    }
  });
  chkBtn.classList.add('kda-settings');
  chkBtn.classList.toggle('kda-on', CHECK);
  chkBtn.title = L.checkOn;

  var goBtn = mkBtn(L.check, function () {
    withRefs(function (ok) { if (ok) { runCheck(true); } });
  });
  goBtn.classList.add('kda-primary');

  function syncCheckUI() {
    var show = CHECK && CHECK_MODE === 'manual' && !!TARGET;
    goBtn.style.display = show ? '' : 'none';
  }

  var ctr = document.createElement('span');
  ctr.id = 'kda-ctr';

  var sep = document.createElement('span');
  sep.id = 'kda-sep';

  var msg = document.createElement('div');
  msg.id = 'kda-msg';

  bar.appendChild(clrBtn);
  bar.appendChild(undBtn);
  bar.appendChild(goBtn);
  bar.appendChild(ctr);
  bar.appendChild(sep);
  bar.appendChild(gridBtn);
  bar.appendChild(keepBtn);
  bar.appendChild(restBtn);
  bar.appendChild(chkBtn);
  if (!TARGET) { chkBtn.style.display = 'none'; }
  syncCheckUI();
  outer.appendChild(cvs);
  wrap.appendChild(outer);
  wrap.appendChild(bar);
  wrap.appendChild(msg);

  if (IS_BACK) {
    wrap.classList.add('kda-back');
    // Hide editing controls — back is read-only compare view
    clrBtn.style.display  = 'none';
    undBtn.style.display  = 'none';
    goBtn.style.display   = 'none';
    gridBtn.style.display = 'none';
    keepBtn.style.display = 'none';
    restBtn.style.display = 'none';
    chkBtn.style.display  = 'none';
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

  function paintStroke(pts, color) {
    if (pts.length < 2) { return; }
    ctx.save();
    ctx.strokeStyle = color || SC; ctx.lineWidth = SW;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
    for (var i = 1; i < pts.length; i++) { ctx.lineTo(pts[i].x, pts[i].y); }
    ctx.stroke(); ctx.restore();
  }

  function redraw() {
    ctx.clearRect(0, 0, SZ, SZ);
    ctx.fillStyle = BG; ctx.fillRect(0, 0, SZ, SZ);
    drawGrid();
    ghosts.forEach(paintGhost);
    strokes.forEach(function (pts, i) {
      paintStroke(pts, VERDICT_COLORS[verdicts[i]] || SC);
    });
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
  function fitTransform(drawnList, refList) {
    if (drawnList.length < 3) { return IDENTITY; }
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

  /* Greedy sequential matching. Each drawn stroke is matched against the
     best still-unclaimed reference stroke; comparing against the expected
     one alone could not tell "wrong stroke" apart from "right stroke, drawn
     too early", which is exactly the mistake stroke-order practice is for.
     A stroke that matches nothing consumes the expected slot anyway so the
     rest of the character still lines up. */
  function evaluate(drawnList, refs, seed) {
    var used = [], pairsD = [], pairsR = [], v = [], errs = [], refOf = [];
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
        var score = Math.min(fwd, rev);
        var lr = pathLength(refPts) / SZ, ld = pathLength(drawnList[i]) / SZ;
        var badLen = Math.max(lr, ld) > LEN_MIN &&
                     (ld > lr * LEN_RATIO || lr > ld * LEN_RATIO);
        if (!best || score < best.score) {
          best = { j: j, score: score, rev: rev < fwd * REV_RATIO,
                   badLen: badLen };
        }
      }
      if (!best || best.score > MATCH_TH * TOL) {
        // Nothing this could be. Consume the slot it should have filled so
        // the strokes after it are still judged against the right shapes.
        v.push('bad');
        errs.push(fmt(L.eBad, { i: i + 1 }));
        refOf.push(expected);
        if (expected !== -1) { used[expected] = true; }
        continue;
      }
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
    return { v: v, errs: errs, xf: xfFinal, refOf: refOf,
             ok: v.filter(function (x) { return x === 'ok'; }).length };
  }

  function summarize(r, refs, drawnCount) {
    var parts = [];
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

  var verdicts = [], ghosts = [], REFS = null, CHECKED = false;

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

  function say(text, good) {
    msg.textContent = text;
    msg.style.display = text ? 'block' : 'none';
    msg.classList.toggle('kda-good', !!good && !!text);
    msg.classList.toggle('kda-bad', !good && !!text);
  }

  /* Runs a full pass over everything drawn so far. Re-running from scratch
     on every stroke (rather than judging only the newest one) keeps live
     and on-demand checking in exact agreement, and lets an earlier verdict
     be revised once later strokes reveal how big the writing really is.
     `full` asks for the whole-character summary; live checking only reports
     the newest stroke until the character is complete. */
  function runCheck(full) {
    if (!REFS || !strokes.length) { return; }
    // Measure how big and where the writing is before judging any of it:
    // the reference prefix of the same length is what a writer who is on
    // track has produced, so their bounding boxes should coincide.
    var seed = fitTransform(strokes, REFS.slice(0, Math.min(strokes.length, REFS.length)));
    var r = evaluate(strokes, REFS, seed === IDENTITY ? null : seed);
    // Once strokes are paired up, refit on the pairs alone — that drops any
    // stroke that was never going to match out of the measurement.
    if (r.xf !== IDENTITY && r.xf !== seed) { r = evaluate(strokes, REFS, r.xf); }
    verdicts = r.v;
    ghosts = [];
    // Show the expected shape only for strokes that went wrong, and only
    // when asked for the full verdict — a ghost after every slip during
    // live practice turns into tracing rather than recall.
    if (full) {
      for (var i = 0; i < r.v.length; i++) {
        var ri = r.refOf[i];
        if (r.v[i] !== 'ok' && ri >= 0) { ghosts.push(applyXf(REFS[ri], r.xf)); }
      }
    }
    CHECKED = true;
    redraw();
    var done = full || strokes.length >= REFS.length;
    if (done) {
      var s = summarize(r, REFS, strokes.length);
      say(s.text, s.good);
    } else {
      var last = r.v[r.v.length - 1];
      say(last === 'ok' ? fmt(L.okStroke, { i: r.v.length })
                        : r.errs[r.errs.length - 1], last === 'ok');
    }
    return r;
  }

  // Pulls the reference in (loading the data file the first time) and then
  // runs `after`. Keeps every caller free of the loading dance.
  function withRefs(after) {
    if (REFS) { after(true); return; }
    if (!TARGET) { after(false); return; }
    withData(function (ok) {
      if (!ok) { say(L.noData, false); after(false); return; }
      REFS = refFor(TARGET);
      if (!REFS) { say(fmt(L.noChar, { c: TARGET }), false); after(false); return; }
      after(true);
    });
  }

  function checkingPossible() { return CHECK && !!TARGET; }

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

  // Called when a stroke is finished. In live mode this judges the stroke
  // right away; in manual mode it only refreshes an already-shown verdict,
  // so drawing after checking doesn't leave a stale message on screen.
  function afterStroke() {
    if (!checkingPossible()) { return; }
    if (CHECK_MODE === 'live') {
      withRefs(function (ok) { if (ok) { runCheck(false); } });
    } else if (CHECKED) {
      say(''); ghosts = []; verdicts = []; CHECKED = false; redraw();
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
    cur = []; redraw(); tick(); afterStroke();
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

  // A restored front drawing, or the back side showing what was written on
  // the front, both arrive with strokes already in place — judge them right
  // away instead of waiting for the next stroke that may never come. The
  // back always gets the full verdict since it is the compare view.
  if (checkingPossible() && strokes.length) {
    withRefs(function (ok) {
      if (ok) { runCheck(IS_BACK || CHECK_MODE === 'manual'); }
    });
  }
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
