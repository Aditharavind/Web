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

test('quote builder prepares WhatsApp and email links from the entered details', () => {
  const field = (value) => ({ value });
  const fields = { product: field('2" gate valve'), qty: field('20 pcs'), place: field('Ruwais') };
  const whatsapp = { href: 'default-wa' };
  const mail = { href: 'default-mail' };
  const form = Object.assign(element(), {
    dataset: { rfqPhone: '+971 50 546 4847', rfqEmail: 'info@example.com' },
    querySelector: (selector) => ({
      '[data-rfq-whatsapp]': whatsapp,
      '[data-rfq-mail]': mail,
      '[data-rfq-product]': fields.product,
      '[data-rfq-qty]': fields.qty,
      '[data-rfq-place]': fields.place,
    })[selector],
  });
  const events = {};
  runInNewContext(source('quote.js'), {
    encodeURIComponent,
    window: { addEventListener: (name, callback) => { events[name] = callback; } },
    document: { querySelectorAll: () => [form] },
  });
  events.DOMContentLoaded();
  form.events.input();
  assert.match(whatsapp.href, /^https:\/\/wa\.me\/971505464847\?text=/);
  assert.match(decodeURIComponent(whatsapp.href), /Quantity: 20 pcs/);
  assert.match(mail.href, /^mailto:info@example\.com\?subject=/);
  fields.product.value = fields.qty.value = fields.place.value = '';
  form.events.input();
  assert.equal(whatsapp.href, 'default-wa');
});
