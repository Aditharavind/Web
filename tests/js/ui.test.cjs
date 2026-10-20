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

test('upload previews preserve selection order and release old URLs', () => {
  class Input {}
  const input = Object.assign(new Input(), element(), { files: ['first', 'second'], dataset: {previewTarget: 'preview'} });
  const grid = element();
  const zone = Object.assign(element(), { querySelector: () => input });
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
    URL: { createObjectURL: (file) => `blob:${file}`, revokeObjectURL: (url) => revoked.push(url) },
  });
  events.DOMContentLoaded();
  input.events.change();
  assert.deepEqual(grid.children.map(item => item.children[0].src), ['blob:first', 'blob:second']);
  input.files = ['replacement'];
  input.events.change();
  assert.deepEqual(grid.children.map(item => item.children[0].src), ['blob:replacement']);
  assert.deepEqual(revoked, ['blob:first', 'blob:second']);
  events.pagehide();
  assert.equal(revoked.at(-1), 'blob:replacement');
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
