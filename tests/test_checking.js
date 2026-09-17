/* Tests for stroke checking, driving the real injected card script.
 *
 * Run with:  node tests/test_checking.js
 *
 * "Writing" a character means replaying its own reference strokes through
 * the canvas's pointer handlers, optionally distorted — shrunk, jittered,
 * reordered, reversed — so each test states a specific way of writing and
 * the verdict it should earn. */

'use strict';

const {
  loadStrokeData, referenceStrokes, makeEnv, runCard, drawStroke,
} = require('./dom_stub');

const SIZE = 300;
const DATA = loadStrokeData();

let failures = 0;
function check(name, cond, detail) {
  if (cond) {
    console.log('  ok   ' + name);
  } else {
    failures++;
    console.log('  FAIL ' + name + (detail ? '\n         ' + detail : ''));
  }
}

function write(char, transform, opts) {
  const env = makeEnv(Object.assign(
    { expected: char, strokeData: DATA, size: SIZE }, opts || {}));
  const ui = runCard(env);
  let strokes = referenceStrokes(DATA, char, SIZE);
  if (transform) { strokes = transform(strokes.map((s) => s.slice())); }
  strokes.forEach((s) => drawStroke(ui.canvas, s));
  return { env, ui, strokes };
}

function pressCheck(env) {
  // The Check button lives in the single cell's own bar on a one-character
  // card and in the shared settings row when there are several.
  const bar = env.doc.getElementById('kda-settings-bar')
           || env.doc.getElementById('kda-bar-0');
  bar.children.find(
    (c) => c.tagName === 'button' && c.textContent === 'Check')._fire('click', {});
}

/* Whole-character verdicts belong to manual mode (and to the answer side):
 * while writing, nothing can tell "not finished yet" from "finished, one
 * stroke short", so live mode deliberately reports stroke by stroke until
 * the expected stroke count is reached. */
function verdict(char, transform, opts) {
  const r = write(char, transform,
                  Object.assign({ checkMode: 'manual' }, opts || {}));
  pressCheck(r.env);
  return r;
}

// ── Baselines ────────────────────────────────────────────────────────

console.log('perfect writing');
['漢', '一', '日', '国', '永', '鬱'].forEach((ch) => {
  const { ui, strokes } = write(ch);
  check(ch + ' (' + strokes.length + ' strokes) is accepted',
        /^Correct/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
});

// ── Tolerance for how people actually write ──────────────────────────

console.log('\nrealistic distortions still accepted');

function scale(factor, ox, oy) {
  return (strokes) => strokes.map((s) => s.map((p) => ({
    x: p.x * factor + (ox || 0), y: p.y * factor + (oy || 0),
  })));
}

// Deterministic pseudo-random jitter — a fixed seed keeps the test stable.
function jitter(amount) {
  let seed = 7;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff - 0.5;
  };
  return (strokes) => strokes.map((s) => s.map((p) => ({
    x: p.x + rnd() * amount, y: p.y + rnd() * amount,
  })));
}

{
  const { ui } = write('漢', scale(0.75, 35, 35));
  check('writing at 75% size, centred', /^Correct/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('漢', jitter(SIZE * 0.025));
  check('shaky hand (±2.5% jitter)', /^Correct/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('国', (s) => jitter(SIZE * 0.02)(scale(0.85, 20, 22)(s)));
  check('small and shaky together', /^Correct/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}

/* The two numbers that matter pull against each other: loose enough for
 * handwriting that is merely imperfect, tight enough that a different
 * character is not waved through. These two sweeps pin both ends down, so
 * that tuning one can't quietly ruin the other. */
{
  const rng = (s) => () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff - 0.5;
  };
  const offsetStrokes = (amount) => (strokes) => {
    const r = rng(3);
    return strokes.map((s) => {
      const dx = r() * amount, dy = r() * amount;
      return s.map((p) => ({ x: p.x + dx, y: p.y + dy }));
    });
  };
  const rotate = (deg) => (strokes) => {
    const t = deg * Math.PI / 180, c = Math.cos(t), si = Math.sin(t), C = SIZE / 2;
    return strokes.map((s) => s.map((p) => ({
      x: C + (p.x - C) * c - (p.y - C) * si,
      y: C + (p.x - C) * si + (p.y - C) * c,
    })));
  };
  const shear = (k) => (strokes) => strokes.map((s) => s.map((p) => ({
    x: p.x + (p.y - SIZE / 2) * k, y: p.y,
  })));
  const chars = ['漢', '国', '語', '愛', '書', '日', '花', '食'];

  [['strokes misplaced by 7%', offsetStrokes(SIZE * 0.07)],
   ['rotated 5°', rotate(5)],
   ['sheared', shear(0.1)],
   ['half size, in a corner', scale(0.5, 8, 8)],
   ['misplaced, rotated and shaky at once',
    (s) => jitter(SIZE * 0.03)(rotate(4)(offsetStrokes(SIZE * 0.04)(s)))],
  ].forEach(([name, distort]) => {
    const rejected = chars.filter(
      (c) => !/^Correct/.test(verdict(c, distort).ui.msg.textContent));
    check('imperfect writing accepted: ' + name, rejected.length === 0,
          'rejected: ' + rejected.join(' '));
  });

  // Pairs that differ only by a stroke's length or a small shape detail —
  // the hardest thing to tell apart without also rejecting sloppy writing.
  const confusable = [
    ['土', '士'], ['士', '土'], ['未', '末'], ['末', '未'], ['刀', '力'],
    ['力', '刀'], ['千', '干'], ['干', '千'], ['田', '由'], ['由', '田'],
    ['牛', '午'], ['午', '牛'], ['人', '入'], ['入', '人'], ['休', '体'],
    ['体', '休'], ['木', '本'], ['本', '木'], ['日', '目'], ['大', '犬'],
    ['右', '左'], ['左', '右'],
  ];
  const accepted = confusable.filter(([target, written]) => {
    const env = makeEnv({ expected: target, strokeData: DATA, size: SIZE,
                          checkMode: 'manual' });
    const ui = runCard(env);
    referenceStrokes(DATA, written, SIZE).forEach((s) => drawStroke(ui.canvas, s));
    pressCheck(env);
    return /^Correct/.test(ui.msg.textContent);
  });
  check('confusable characters are told apart', accepted.length === 0,
        'wrongly accepted: ' + accepted.map((p) => p.join('/')).join(' '));
}

// ── Mistakes it must catch ───────────────────────────────────────────

console.log('\nmistakes are reported');

{
  const { ui } = write('漢', (s) => { const t = s.slice();
    const tmp = t[3]; t[3] = t[4]; t[4] = tmp; return t; });
  check('two strokes swapped → out of order',
        /out of order/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('漢', (s) => { const t = s.slice();
    t[6] = t[6].slice().reverse(); return t; });
  check('one stroke drawn backwards → backwards',
        /backwards/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
}
{
  const { ui } = verdict('漢', (s) => s.slice(0, s.length - 1));
  check('one stroke left out → missing',
        /1 stroke\(s\) missing/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('漢', (s) => s.concat([[
    { x: 40, y: 250 }, { x: 260, y: 255 }]]));
  check('an extra stroke → too many',
        /1 stroke\(s\) too many/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}
{
  // Writing the wrong character entirely: 漢's strokes on a 語 card.
  const env = makeEnv({ expected: '語', strokeData: DATA, size: SIZE,
                        checkMode: 'manual' });
  const ui = runCard(env);
  referenceStrokes(DATA, '漢', SIZE).forEach((s) => drawStroke(ui.canvas, s));
  pressCheck(env);
  const okCount = (ui.msg.textContent.match(/(\d+) of \d+ strokes correct/) || [])[1];
  check('a different character is not accepted',
        !/^Correct/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
  check('a different character scores poorly',
        okCount !== undefined && Number(okCount) <= 4,
        'got: ' + ui.msg.textContent);
}

// ── Modes and opt-out ────────────────────────────────────────────────

console.log('\nmodes');

{
  const { ui } = write('日', (s) => s.slice(0, 2));
  check('live mode judges each stroke before the character is finished',
        /stroke 2/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('日', null, { checkMode: 'manual' });
  check('manual mode stays quiet until asked',
        ui.msg.textContent === '', 'got: ' + ui.msg.textContent);
}
{
  const { ui } = verdict('日');
  check('pressing Check reports the verdict',
        /^Correct/.test(ui.msg.textContent), 'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('日', null, { check: '0' });
  check('checking off → no verdict shown',
        ui.msg.textContent === '', 'got: ' + ui.msg.textContent);
}
{
  const { ui } = write('日', null, { expected: '' });
  check('no expected character → no verdict shown',
        ui.msg.textContent === '', 'got: ' + ui.msg.textContent);
}
{
  const env = makeEnv({ expected: '日', strokeData: DATA, size: SIZE,
                        storage: { kda_check: '0' } });
  const ui = runCard(env);
  referenceStrokes(DATA, '日', SIZE).forEach((s) => drawStroke(ui.canvas, s));
  check('the saved off-switch overrides the injected default',
        ui.msg.textContent === '', 'got: ' + ui.msg.textContent);
}
{
  // A character KanjiVG has no entry for must degrade gracefully.
  const { ui } = write('日', null, { expected: '가' });
  check('a character without reference data is handled',
        ui.msg.textContent === '' || /No reference/.test(ui.msg.textContent),
        'got: ' + ui.msg.textContent);
}

// ── The answer side ──────────────────────────────────────────────────

console.log('\nanswer side');
{
  // The back shows what was written on the front, so it gets the full
  // verdict without anyone pressing anything.
  const incomplete = referenceStrokes(DATA, '漢', SIZE).slice(0, 12);
  const env = makeEnv({ expected: '漢', strokeData: DATA, size: SIZE,
                        isBack: true,
                        storage: { kda_last_strokes: JSON.stringify(incomplete) } });
  runCard(env);
  const msg = env.doc.getElementById('kda-msg-0');
  check('an unfinished character is reported on the answer side',
        /1 stroke\(s\) missing/.test(msg.textContent),
        'got: ' + msg.textContent);
}
{
  const complete = referenceStrokes(DATA, '日', SIZE);
  const env = makeEnv({ expected: '日', strokeData: DATA, size: SIZE,
                        isBack: true,
                        storage: { kda_last_strokes: JSON.stringify(complete) } });
  runCard(env);
  const msg = env.doc.getElementById('kda-msg-0');
  check('a correct character is confirmed on the answer side',
        /^Correct/.test(msg.textContent), 'got: ' + msg.textContent);
}

// ── Drawing still works with checking involved ───────────────────────

console.log('\ndrawing itself is unaffected');
{
  const { ui, env } = write('日');
  check('stroke counter still counts', /Strokes: 4/.test(ui.counter.textContent),
        'got: ' + ui.counter.textContent);
  // Storage holds one stroke list per canvas, so a one-character card
  // saves a single list of four strokes.
  const saved = JSON.parse(env.store.kda_last_strokes || '[]');
  check('strokes are still saved for the answer side',
        saved.length === 1 && saved[0].length === 4,
        'got: ' + JSON.stringify(saved.map((c) => c.length)));
}

// ── More than one character per card ─────────────────────────────────

console.log('\nmultiple characters');

function writeWord(field, written, opts) {
  const env = makeEnv(Object.assign(
    { expected: field, strokeData: DATA, size: SIZE }, opts || {}));
  const ui = runCard(env);
  written.forEach((ch, i) => {
    if (!ch || !ui.cells[i]) { return; }
    referenceStrokes(DATA, ch, SIZE).forEach(
      (s) => drawStroke(ui.cells[i].canvas, s));
  });
  return { env, ui };
}

{
  const { ui } = writeWord('漢字', ['漢', '字']);
  check('a two-character field gets two canvases', ui.cells.length === 2,
        'got ' + ui.cells.length);
  check('both characters are checked',
        ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  // Right first character, wrong second — each canvas answers for itself.
  const { ui } = writeWord('漢字', ['漢', '学']);
  check('a wrong character is reported on its own canvas',
        /^Correct/.test(ui.cells[0].msg.textContent)
          && !/^Correct/.test(ui.cells[1].msg.textContent),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  const { ui } = writeWord('図書館', ['図', '書', '館']);
  check('three characters, all three checked',
        ui.cells.length === 3
          && ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  // A field carrying its reading must not turn the reading into canvases.
  const { ui } = writeWord('漢字[かんじ]', ['漢', '字']);
  check('furigana readings do not become canvases', ui.cells.length === 2,
        'got ' + ui.cells.length);
  check('the characters themselves are still checked',
        ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  const { ui } = writeWord('食べる', ['食', 'べ', 'る']);
  check('kana get canvases and references too',
        ui.cells.length === 3
          && ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  const env = makeEnv({ expected: '今日は良い天気ですね今日も', strokeData: DATA,
                        size: SIZE });
  const ui = runCard(env);
  check('a sentence is capped at eight canvases', ui.cells.length === 8,
        'got ' + ui.cells.length);
}
{
  const env = makeEnv({ expected: 'hello', strokeData: DATA, size: SIZE });
  const ui = runCard(env);
  check('a field with no CJK still gives one plain canvas',
        ui.cells.length === 1 && ui.cells[0].msg.textContent === '');
}
{
  // Front to back: every canvas's strokes must survive the flip.
  const front = writeWord('漢字', ['漢', '字']);
  const back = makeEnv({ expected: '漢字', strokeData: DATA, size: SIZE,
                         isBack: true, storage: front.env.store });
  const ui = runCard(back);
  check('both canvases come back on the answer side',
        ui.cells.length === 2
          && ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  // A drawing saved by the pre-multi-character version is a bare stroke
  // list; it must still land on the first canvas rather than being lost.
  const old = JSON.stringify(referenceStrokes(DATA, '漢', SIZE));
  const env = makeEnv({ expected: '漢', strokeData: DATA, size: SIZE,
                        isBack: true, storage: { kda_last_strokes: old } });
  const ui = runCard(env);
  check('a drawing saved by the older format still restores',
        /^Correct/.test(ui.cells[0].msg.textContent),
        'got: ' + ui.cells[0].msg.textContent);
}
{
  const { env, ui } = writeWord('漢字', ['漢', '字']);
  const saved = JSON.parse(env.store.kda_last_strokes || '[]');
  check('each canvas is saved separately',
        saved.length === 2 && saved[0].length === 13 && saved[1].length === 6,
        'got: ' + JSON.stringify(saved.map((c) => c.length)));
  check('the settings row appears once, not per canvas',
        !!env.doc.getElementById('kda-settings-bar')
          && !ui.cells[0].bar.children.some((c) => c.textContent === '✓'),
        'settings duplicated into a cell bar');
}
{
  const { env, ui } = writeWord('漢字', ['漢', '字'], { checkMode: 'manual' });
  check('manual mode stays quiet across every canvas',
        ui.cells.every((c) => c.msg.textContent === ''),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
  pressCheck(env);
  check('one Check press judges every canvas',
        ui.cells.every((c) => /^Correct/.test(c.msg.textContent)),
        'got: ' + ui.cells.map((c) => c.msg.textContent).join(' | '));
}
{
  // Leaving a character out entirely: the Check button must say so rather
  // than quietly passing the blank canvas over.
  const { env, ui } = writeWord('漢字', ['漢', null], { checkMode: 'manual' });
  pressCheck(env);
  check('a character left blank is reported as missing',
        /missing/.test(ui.cells[1].msg.textContent),
        'got: ' + ui.cells[1].msg.textContent);
}

console.log(failures ? '\n' + failures + ' failing' : '\nall passing');
process.exit(failures ? 1 : 0);
