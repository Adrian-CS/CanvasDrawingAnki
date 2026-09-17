/* Minimal DOM stand-in for running the injected card script under node.
 *
 * The canvas script is plain ES5 against a handful of DOM APIs, so stubbing
 * those is enough to drive the real code — including its pointer handling —
 * without a browser. Anything the script does not touch is left out on
 * purpose: this is a test fixture, not a DOM implementation. */

'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function extractCanvasJs() {
  const src = fs.readFileSync(
    path.join(__dirname, '..', 'drawing', 'template.py'), 'utf8');
  const open = '_CANVAS_JS = r"""';
  const from = src.indexOf(open);
  if (from === -1) { throw new Error('canvas script not found in template.py'); }
  const to = src.indexOf('"""', from + open.length);
  return src.slice(from + open.length, to);
}

function loadStrokeData() {
  const gz = fs.readFileSync(
    path.join(__dirname, '..', 'drawing', 'data', 'strokes.js.gz'));
  const js = zlib.gunzipSync(gz).toString('utf8');
  const sandbox = { window: {} };
  new Function('window', js)(sandbox.window);
  return sandbox.window.KDA_STROKE_DATA;
}

const A64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/** Reference strokes for `ch`, in canvas pixels — the same shapes the card
 *  script will compare against, so a test can "write" a flawless character. */
function referenceStrokes(data, ch, size) {
  const at = data.indexOf('\n' + ch + '|');
  if (at === -1) { return null; }
  const from = at + ch.length + 2;
  const to = data.indexOf('\n', from);
  const body = data.slice(from, to === -1 ? data.length : to);
  return body.split(',').map((t) => {
    const pts = [];
    for (let i = 0; i + 1 < t.length; i += 2) {
      pts.push({ x: A64.indexOf(t[i]) / 63 * size,
                 y: A64.indexOf(t[i + 1]) / 63 * size });
    }
    return pts;
  });
}

class Element {
  constructor(tag, doc) {
    this.tagName = tag;
    this._doc = doc;
    this._id = '';
    this.style = {};
    this.textContent = '';
    this.children = [];
    this.dataset = {};
    this.listeners = {};
    this.disabled = false;
    this.open = false;
    this.width = 0;
    this.height = 0;
    this._classes = new Set();
    this.classList = {
      add: (c) => this._classes.add(c),
      remove: (c) => this._classes.delete(c),
      contains: (c) => this._classes.has(c),
      toggle: (c, on) => {
        const want = on === undefined ? !this._classes.has(c) : !!on;
        if (want) { this._classes.add(c); } else { this._classes.delete(c); }
      },
    };
  }
  get id() { return this._id; }
  set id(v) { this._id = v; if (v) { this._doc._byId.set(v, this); } }
  appendChild(child) {
    this.children.push(child);
    if (child._id) { this._doc._byId.set(child._id, child); }
    if (child.tagName === 'script' && child.src) { child._fire('error', {}); }
    return child;
  }
  insertAdjacentElement(_where, el) {
    this.children.push(el);
    if (el._id) { this._doc._byId.set(el._id, el); }
    return el;
  }
  addEventListener(type, fn) {
    (this.listeners[type] = this.listeners[type] || []).push(fn);
  }
  _fire(type, ev) {
    (this.listeners[type] || []).forEach((fn) => fn(ev));
  }
  setPointerCapture() {}
  getBoundingClientRect() {
    return { left: 0, top: 0, width: this.width, height: this.height };
  }
  getContext() { return makeCtx(); }
}

/* A canvas context that records nothing — the assertions in these tests are
 * about verdicts and messages, not pixels. */
function makeCtx() {
  const noop = () => {};
  return {
    save: noop, restore: noop, beginPath: noop, moveTo: noop, lineTo: noop,
    stroke: noop, clearRect: noop, fillRect: noop, setLineDash: noop,
  };
}

/** Build a fresh global environment with one card rendered in it. */
function makeEnv(opts) {
  const o = Object.assign({
    size: 300, expected: '', isBack: false, check: '1',
    checkMode: 'live', tol: '1', lang: 'en', body: '<div>card</div>',
    strokeData: null, storage: {},
  }, opts);

  const doc = { _byId: new Map() };
  doc.createElement = (tag) => new Element(tag, doc);
  doc.getElementById = (id) => doc._byId.get(id) || null;
  doc.head = new Element('head', doc);
  doc.body = new Element('body', doc);
  doc.body.innerHTML = o.body;

  const anchor = new Element('div', doc);
  anchor.id = 'kda-anchor';
  Object.assign(anchor.dataset, {
    size: String(o.size), grid: 'tian', sw: '3', sc: '#1a1a1a',
    gc: '#aaaaaa', bg: '#ffffff', persist: '1', restore: '1',
    keepWindow: '90', check: o.check, checkMode: o.checkMode,
    tol: o.tol, lang: o.lang,
  });
  if (o.expected) {
    const span = new Element('span', doc);
    span.id = 'kda-expected';
    span.textContent = o.expected;
    anchor.appendChild(span);
  }
  if (o.isBack) {
    const hr = new Element('hr', doc);
    hr.id = 'answer';
  }

  const store = Object.assign({}, o.storage);
  const localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  };

  const win = { KDA_STROKE_DATA: o.strokeData || undefined };
  return { doc, win, localStorage, store, navigator: { language: o.lang } };
}

/** Every canvas the card built, in order — one per character checked. */
function cellsOf(doc) {
  const out = [];
  for (let i = 0; ; i++) {
    const canvas = doc.getElementById('kda-canvas-' + i);
    if (!canvas) { return out; }
    out.push({
      canvas,
      msg: doc.getElementById('kda-msg-' + i),
      counter: doc.getElementById('kda-ctr-' + i),
      bar: doc.getElementById('kda-bar-' + i),
    });
  }
}

/** Run the card script inside an environment built by makeEnv(). */
function runCard(env) {
  const js = extractCanvasJs();
  const fn = new Function(
    'document', 'window', 'localStorage', 'navigator', js);
  fn(env.doc, env.win, env.localStorage, env.navigator);
  const cells = cellsOf(env.doc);
  // Most tests drive a single-character card, so the first cell's parts are
  // exposed directly; `cells` is there for the multi-character ones.
  return Object.assign({ cells }, cells[0]);
}

/** Draw one stroke on the canvas as a real pointer would. */
function drawStroke(canvas, pts) {
  canvas._fire('pointerdown', {
    preventDefault() {}, pointerId: 1, clientX: pts[0].x, clientY: pts[0].y,
  });
  pts.slice(1).forEach((p) => {
    canvas._fire('pointermove', {
      preventDefault() {}, pointerId: 1, clientX: p.x, clientY: p.y,
    });
  });
  const last = pts[pts.length - 1];
  canvas._fire('pointerup', {
    preventDefault() {}, pointerId: 1, clientX: last.x, clientY: last.y,
  });
}

module.exports = {
  extractCanvasJs, loadStrokeData, referenceStrokes,
  makeEnv, runCard, drawStroke, cellsOf,
};
