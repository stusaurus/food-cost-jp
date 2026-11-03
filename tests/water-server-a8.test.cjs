const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const file = path.join(__dirname, '..', 'site', 'guides', 'water-server-vs-bottled-water', 'index.html');
const expectedA8 = 'https://px.a8.net/svt/ejp?a8mat=4BGCF1+53DLEY+2B8Y+15OK2A';
const expectedPixel = 'https://www17.a8.net/0.gif?a8mat=4BGCF1+53DLEY+2B8Y+15OK2A';

function boot(query = '?test=1') {
  const html = fs.readFileSync(file, 'utf8');
  const events = [];
  const dom = new JSDOM(html, {
    url: 'https://stusaurus.github.io/food-cost-jp/guides/water-server-vs-bottled-water/' + query,
    runScripts: 'dangerously',
    beforeParse(window) {
      window.gtag = (...args) => events.push(args);
    }
  });
  const document = dom.window.document;
  const set = (id, value) => { document.getElementById(id).value = String(value); };
  const click = (id) => { document.getElementById(id).click(); };
  return { dom, document, events, set, click };
}

function fillTypical({ set }) {
  Object.entries({
    'liters': 48, 'bottle-liters': 2, 'case-count': 6,
    'case-price': 900, 'case-shipping': 0, 'monthly-fee': 3000,
    'server-per-liter': 0, 'electric': 500, 'upfront': 0
  }).forEach(([id, value]) => set(id, value));
}

test('real water calculator works with precise annual purchase count and honest recommendation', () => {
  const b = boot();
  fillTypical(b);
  b.click('calculate');
  const text = id => b.document.getElementById(id).textContent;
  assert.equal(text('bottle-year'), '43,200円');
  assert.equal(text('server-year'), '42,000円');
  assert.equal(text('bottle-count'), '288本（48ケース）');
  assert.equal(text('purchased-liters'), '576L');
  assert.equal(text('used-liters'), '576L');
  assert.match(text('verdict'), /サーバーが年間1,200円安い/);
  assert.ok(b.document.getElementById('results').classList.contains('visible'));

  b.set('monthly-fee', 8000);
  b.click('calculate');
  assert.equal(text('bottle-year'), '43,200円');
  assert.match(text('verdict'), /ペットボトルが年間/);
  b.dom.window.close();
});

test('changing annual cost inputs hides stale results until explicitly recalculated', () => {
  const b = boot();
  try {
    fillTypical(b);
    b.click('calculate');
    const results = b.document.getElementById('results');
    const error = b.document.getElementById('error');
    assert.ok(results.classList.contains('visible'));
    assert.equal(b.document.getElementById('server-year').textContent, '42,000円');
    const monthly = b.document.getElementById('monthly-fee');
    monthly.value = '8000';
    monthly.dispatchEvent(new b.dom.window.Event('input', { bubbles: true }));
    assert.ok(!results.classList.contains('visible'), 'Old calculated annual price must be hidden after input');
    assert.match(error.textContent, /条件が変わりました/);
    b.click('calculate');
    assert.ok(results.classList.contains('visible'));
    assert.equal(b.document.getElementById('server-year').textContent, '102,000円');
    const count = b.document.getElementById('case-count');
    count.value = '12';
    count.dispatchEvent(new b.dom.window.Event('change', { bubbles: true }));
    assert.ok(!results.classList.contains('visible'), 'Change event must also invalidate old quotes');
    assert.equal(b.events.filter(e => e[1] === 'affiliate_click').length, 0);
  } finally { b.dom.window.close(); }
});

test('fractional yen input is rejected instead of silently rounding checkout cost', () => {
  const b = boot();
  try {
    fillTypical(b);
    b.set('case-price', '900.5');
    b.click('calculate');
    const results = b.document.getElementById('results');
    const error = b.document.getElementById('error');
    assert.ok(!results.classList.contains('visible'));
    assert.match(error.textContent, /金額・ケース本数は整数/);
    b.set('case-price', '900');
    b.click('calculate');
    assert.ok(results.classList.contains('visible'));
    assert.equal(b.document.getElementById('bottle-year').textContent, '43,200円');
  } finally { b.dom.window.close(); }
});

test('official A8 creative and attribution pixel are exact and ad is clearly disclosed', () => {
  const b = boot();
  const ad = b.document.getElementById('a8-every-frecious-ad');
  assert.ok(ad);
  assert.match(ad.textContent, /広告｜A8.netアフィリエイト/);
  const link = ad.querySelector('a');
  assert.equal(link.getAttribute('href'), expectedA8);
  assert.equal(link.getAttribute('rel'), 'nofollow');
  assert.match(link.textContent, /every frecious（エブリィフレシャス）/);
  assert.equal(ad.querySelector('img').getAttribute('src'), expectedPixel);
  assert.equal(ad.querySelector('img').getAttribute('width'), '1');
  assert.equal(b.document.querySelectorAll('a[href^="https://px.a8.net"]').length, 1);
  b.dom.window.close();
});

test('outbound A8 event carries correct site and operator-test flag without modifying link', () => {
  const b = boot('?test=1');
  const ad = b.document.querySelector('#a8-every-frecious-ad a');
  ad.addEventListener('click', ev => ev.preventDefault());
  ad.dispatchEvent(new b.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
  const clicks = b.events.filter(e => e[1] === 'affiliate_click');
  assert.equal(clicks.length, 1);
  assert.equal(clicks[0][2].affiliate, 'a8');
  assert.equal(clicks[0][2].program, 'every_frecious');
  assert.equal(clicks[0][2].site_id, 'food_cost_jp');
  assert.equal(clicks[0][2].operator_test, '1');
  assert.equal(ad.getAttribute('href'), expectedA8);
  b.dom.window.close();
});

test('incomplete input cannot show a fabricated price result', () => {
  const b = boot('');
  b.click('calculate');
  assert.ok(!b.document.getElementById('results').classList.contains('visible'));
  assert.match(b.document.getElementById('error').textContent, /すべての項目/);
  b.dom.window.close();
});
