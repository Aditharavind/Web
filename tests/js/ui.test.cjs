const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const path = require('node:path');
const source = (name) => readFileSync(path.join(__dirname, '../../app/static/js', name), 'utf8');

function element() {
  return { children: [], events: {}, dataset: {},
    addEventListener(name, callback) { this.events[name] = callback; },
    appendChild(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
  };
}

function uploadZone(files, limits = {}) {
  class Input {}
  const input = Object.assign(new Input(), element(), { files, dataset: {previewTarget: 'preview'}, value: 'chosen' });
  const grid = element();
  const note = Object.assign(element(), { hidden: true, textContent: '' });
  const zone = Object.assign(element(), {
    dataset: limits, querySelector: () => input, parentElement: { querySelector: () => note },
  });
  const revoked = [];
  const events = {};
  runInNewContext(source('admin-products.js'), {
    HTMLInputElement: Input,
    window: {addEventListener: (name, callback) => {events[name] = callback;}},
    document: {
      querySelectorAll: (selector) => selector === '[data-upload-zone]' ? [zone] : [],
      getElementById: () => grid,
      createElement: element,
      querySelector: () => null,
      addEventListener() {},
    },
    URL: { createObjectURL: (file) => `blob:${file.name}`, revokeObjectURL: (url) => revoked.push(url) },
  });
  events.DOMContentLoaded();
  return { input, grid, note, revoked, events };
}
const photo = (name, size = 1000) => ({ name, size });

test('upload previews preserve selection order and release old URLs', () => {
  const { input, grid, revoked, events } = uploadZone([photo('a.jpg'), photo('b.png')]);
  input.events.change();
  assert.deepEqual(grid.children.map(item => item.children[0].src), ['blob:a.jpg', 'blob:b.png']);
  input.files = [photo('c.webp')];
  input.events.change();
  assert.deepEqual(grid.children.map(item => item.children[0].src), ['blob:c.webp']);
  assert.deepEqual(revoked, ['blob:a.jpg', 'blob:b.png']);
  events.pagehide();
  assert.equal(revoked.at(-1), 'blob:c.webp');
});

test('invalid uploads are refused in the browser with a clear message and nothing is submitted', () => {
  const limits = { maxFiles: '3', maxBytes: '5000', existing: '2' };
  const cases = [
    [[photo('manual.pdf')], /Only JPG, PNG or WEBP/],
    [[photo('big.jpg', 9000)], /MB or smaller/],
    [[photo('a.jpg'), photo('b.jpg')], /up to 3 images and already has 2/],
  ];
  for (const [files, message] of cases) {
    const { input, note } = uploadZone(files, limits);
    input.events.change();
    assert.match(note.textContent, message);
    assert.equal(note.hidden, false);
    assert.equal(input.value, '');
  }
  const { input, note } = uploadZone([photo('ok.JPG')], limits);
  input.events.change();
  assert.equal(note.hidden, true);
  assert.equal(input.value, 'chosen');
});

test('catalogue search waits for composition and cancels pending category search', () => {
  const input = element(), category = element();
  let timer, submitted = 0;
  const window = {
    addEventListener: (_, callback) => callback(),
    clearTimeout: () => {timer = undefined;},
    setTimeout: (callback) => {timer = callback; return 1;},
  };
  runInNewContext(source('catalog.js'), {
    window,
    document: {
      querySelector: () => input,
      querySelectorAll: () => [category],
      getElementById: () => ({requestSubmit: () => submitted++}),
    },
  });
  input.events.input({isComposing: true});
  assert.equal(timer, undefined);
  input.events.input({isComposing: false});
  assert.equal(typeof timer, 'function');
  category.events.change();
  assert.equal(timer, undefined);
  assert.equal(submitted, 1);
});

test('quote list merges repeated items and builds one message for WhatsApp and email', () => {
  const window = { addEventListener() {} };
  runInNewContext(source('quote.js'), { window });
  const { mergeItem, buildMessage, sanitize } = window.NawaQuote;

  const items = [];
  mergeItem(items, { name: 'Gate valve', spec: '2 in', qty: 5 });
  mergeItem(items, { name: 'gate VALVE', spec: '2 in', qty: 3 });
  mergeItem(items, { name: 'Gate valve', spec: '4 in', qty: 1 });
  mergeItem(items, { name: '   ', qty: 9 });
  assert.equal(items.length, 2);
  assert.equal(items[0].qty, 8);

  const message = buildMessage(items, 'Ruwais');
  assert.match(message, /1\. \*Gate valve\*\n   Spec: 2 in\n   Qty: 8\n\n2\. \*Gate valve\*\n   Spec: 4 in\n   Qty: 1/);
  assert.match(message, /Delivery location: Ruwais/);

  assert.equal(sanitize({ name: 'Seal', qty: -4 }).qty, 1);
  assert.equal(sanitize({ name: 'Seal', qty: 1e9 }).qty, 99999);
  assert.equal(sanitize('not an item'), null);
});

test('mobile menu opens and closes without ever measuring the window', () => {
  const open = new Set();
  const attributes = {};
  const nav = {
    classList: { toggle: (name, on) => (on ? open.add(name) : open.delete(name)), contains: (name) => open.has(name) },
    querySelectorAll: () => [],
  };
  const button = {
    events: {},
    closest: () => nav,
    getAttribute: (name) => (name === 'aria-controls' ? 'menu' : null),
    setAttribute: (name, value) => { attributes[`button ${name}`] = value; },
    addEventListener(name, callback) { this.events[name] = callback; },
  };
  const menu = { setAttribute: (name, value) => { attributes[`menu ${name}`] = value; } };
  const keys = {};
  const events = {};
  const window = {
    matchMedia: () => ({ matches: true }),
    addEventListener: (name, callback) => { events[name] = callback; },
    get innerWidth() { throw new Error('reading the window size forces a layout'); },
  };
  const document = {
    querySelectorAll: (selector) => (selector === '[data-nav-toggle]' ? [button] : []),
    getElementById: () => menu,
    addEventListener: (name, callback) => { keys[name] = callback; },
  };
  runInNewContext(source('ui.js'), { window, document });
  events.DOMContentLoaded();
  assert.equal(attributes['menu aria-hidden'], 'true');
  button.events.click();
  assert.ok(open.has('mobile-open'));
  assert.equal(attributes['button aria-expanded'], 'true');
  assert.equal(attributes['menu aria-hidden'], 'false');
  keys.keydown({ key: 'Escape' });
  assert.ok(!open.has('mobile-open'));
  events.resize();
});
