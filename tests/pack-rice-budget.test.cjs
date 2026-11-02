const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

const script = fs.readFileSync('scripts/pack_rice_budget.js', 'utf8');
function setup() {
  const html = '<!doctype html><html lang="ja"><body>' +
    '<section data-pack-rice-budget><form data-budget-form>' +
    '<select data-budget-product>' +
    '<option value="0" data-price="3600.00" data-count="24">180g×24食</option>' +
    '<option value="1" data-price="4800.00" data-count="24">200g×24食</option>' +
    '</select><input data-budget-daily type="number" value="1">' +
    '<p data-budget-error hidden></p><button type="submit">計算</button>' +
    '</form><div data-budget-results>' +
    '<strong data-budget-days></strong><strong data-budget-month-meals></strong>' +
    '<strong data-budget-boxes></strong><strong data-budget-payment></strong>' +
    '<strong data-budget-left></strong><strong data-budget-unit></strong>' +
    '</div></section></body></html>';
  const dom = new JSDOM(html, {
    url: 'https://stusaurus.github.io/food-cost-jp/guides/pack-rice-24-servings-cost/',
    runScripts: 'outside-only'
  });
  dom.window.eval(script);
  const document = dom.window.document;
  const get = (selector) => document.querySelector('[data-budget-' + selector + ']');
  return { dom, get };
}

test('24-meal guide defaults to 1 serving per day, 2 whole boxes for 30 days', () => {
  const { dom, get } = setup();
  assert.equal(get('days').textContent, '24日');
  assert.equal(get('month-meals').textContent, '30食');
  assert.equal(get('boxes').textContent, '2箱');
  assert.equal(get('payment').textContent, '¥7,200');
  assert.equal(get('left').textContent, '18食');
  assert.equal(get('unit').textContent, '¥150');
  assert.equal(get('error').hidden, true);
  dom.window.close();
});

test('changing usage and real product updates total purchase cost without rounding boxes down', () => {
  const { dom, get } = setup();
  get('daily').value = '2';
  get('daily').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(get('days').textContent, '12日');
  assert.equal(get('boxes').textContent, '3箱');
  assert.equal(get('payment').textContent, '¥10,800');
  get('product').value = '1';
  get('product').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  assert.equal(get('payment').textContent, '¥14,400');
  assert.equal(get('unit').textContent, '¥200');
  assert.equal(get('results').hidden, false);
  dom.window.close();
});

test('0.5 servings/day is permitted; invalid or empty input never presents a stale cost', () => {
  const { dom, get } = setup();
  get('daily').value = '0.5';
  get('daily').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(get('days').textContent, '48日');
  assert.equal(get('boxes').textContent, '1箱');
  for (const invalid of ['', '0', '13']) {
    get('daily').value = invalid;
    get('daily').dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    assert.equal(get('results').hidden, true);
    assert.equal(get('error').hidden, false);
    assert.match(get('error').textContent, /0.5〜12/);
  }
  dom.window.close();
});

test('non-24 options are rejected rather than silently compared', () => {
  const { dom, get } = setup();
  get('product').selectedOptions[0].dataset.count = '40';
  get('product').dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  assert.equal(get('results').hidden, true);
  assert.equal(get('error').hidden, false);
  dom.window.close();
});
