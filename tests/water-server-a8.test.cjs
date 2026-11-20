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
  assert.equal(text('bottle-monthly'), '月平均 3,600円');
  assert.equal(text('server-monthly'), '月平均 3,500円');
  assert.equal(text('bottle-effective'), '使用予定1Lあたり 75.0円／L');
  assert.equal(text('server-effective'), '使用予定1Lあたり 72.9円／L');
  assert.equal(text('bottle-count'), '288本（48セット購入）');
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

test('hypothetical trial is one tap, fully disclosed, and cannot imply a current seller quote', () => {
  const b = boot('');
  try {
    const warning = b.document.getElementById('example-warning');
    assert.equal(warning.hidden, true);
    assert.ok(!b.document.getElementById('results').classList.contains('visible'));
    b.click('example');
    const text = id => b.document.getElementById(id).textContent;
    assert.equal(b.document.getElementById('liters').value, '48');
    assert.equal(b.document.getElementById('bottle-liters').value, '2');
    assert.equal(b.document.getElementById('case-count').value, '6');
    assert.equal(b.document.getElementById('case-price').value, '900');
    assert.equal(b.document.getElementById('monthly-fee').value, '3000');
    assert.equal(warning.hidden, false);
    assert.match(warning.textContent, /仮の数値/);
    assert.match(warning.textContent, /現在の販売価格・各社の契約料金ではありません/);
    assert.equal(text('bottle-year'), '43,200円');
    assert.equal(text('server-year'), '42,000円');
    assert.equal(text('bottle-effective'), '使用予定1Lあたり 75.0円／L');
    assert.ok(b.document.getElementById('results').classList.contains('visible'));
    const fee = b.document.getElementById('monthly-fee');
    fee.value = '8000';
    fee.dispatchEvent(new b.dom.window.Event('input', { bubbles: true }));
    assert.ok(!b.document.getElementById('results').classList.contains('visible'));
    assert.equal(warning.hidden, false, 'Always keep the trial-rate disclaimer visible after edits');
    b.click('calculate');
    assert.equal(text('server-year'), '102,000円');
    assert.equal(text('server-monthly'), '月平均 8,500円');
    assert.equal(b.events.filter(ev => ev[1] === 'affiliate_click').length, 0);
  } finally { b.dom.window.close(); }
});

test('fractional-case annual rounding is not disguised as uniform monthly payment', () => {
  const b = boot();
  try {
    fillTypical(b);
    b.set('liters', '35');
    b.click('calculate');
    const text = id => b.document.getElementById(id).textContent;
    // 35L/month -> 420L/year -> 35 x 12L cases x 900 yen.
    assert.equal(text('bottle-year'), '31,500円');
    assert.equal(text('bottle-monthly'), '月平均 2,625円');
    assert.equal(text('bottle-effective'), '使用予定1Lあたり 75.0円／L');
    assert.match(b.document.querySelector('#results .muted').textContent, /月ごとの支払額は均等ではありません/);
    b.set('liters', '35.1');
    b.click('calculate');
    assert.equal(text('bottle-count'), '216本（36セット購入）');
    assert.equal(text('bottle-year'), '32,400円');
    assert.equal(text('bottle-monthly'), '月平均 2,700円');
  } finally { b.dom.window.close(); }
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

test('verified water seller offers prefill exact unit price without fabricated delivery charges', () => {
  const b = boot('?test=1');
  try {
    const cards = [...b.document.querySelectorAll('[data-water-offer]')];
    assert.ok(cards.length >= 2, 'Saved snapshot must publish both verified 2L and 500ml water options');
    const twoLiter = cards.find(el => el.dataset.bottleLiters === '2');
    const halfLiter = cards.find(el => el.dataset.bottleLiters === '0.5');
    assert.ok(twoLiter);
    assert.ok(halfLiter);
    assert.ok(Number.isInteger(Number(twoLiter.dataset.caseCount)));
    assert.ok(Number.isInteger(Number(twoLiter.dataset.casePrice)));
    const source = b.document.getElementById('bottle-source-note');
    assert.equal(source.hidden, true);
    fillTypical(b);
    b.click('calculate');
    assert.equal(b.document.getElementById('bottle-year').textContent, '43,200円');
    twoLiter.click();
    assert.equal(source.hidden, false);
    assert.ok(!b.document.getElementById('results').classList.contains('visible'));
    assert.equal(b.document.getElementById('bottle-liters').value, twoLiter.dataset.bottleLiters);
    assert.equal(b.document.getElementById('case-count').value, twoLiter.dataset.caseCount);
    assert.equal(b.document.getElementById('case-price').value, twoLiter.dataset.casePrice);
    assert.equal(b.document.getElementById('case-shipping').value, '0');
    b.click('calculate');
    const count = Number(twoLiter.dataset.caseCount);
    const value = Number(twoLiter.dataset.casePrice);
    const expectedSets = Math.ceil(48 * 12 / (2 * count));
    assert.equal(b.document.getElementById('bottle-year').textContent,
      (expectedSets * value).toLocaleString('ja-JP') + '円');
    assert.equal(b.document.getElementById('bottle-count').textContent,
      expectedSets * count + '本（' + expectedSets + 'セット購入）');
    assert.equal(b.events.filter(ev => ev[1] === 'water_offer_prefill').length, 1);
    assert.equal(b.events.find(ev => ev[1] === 'water_offer_prefill')[2].operator_test, '1');
    assert.equal(b.events.filter(ev => ev[1] === 'affiliate_click').length, 0);

    const manualPrice = b.document.getElementById('case-price');
    manualPrice.value = String(Number(manualPrice.value) + 10);
    manualPrice.dispatchEvent(new b.dom.window.Event('input', { bubbles: true }));
    assert.equal(source.hidden, true, 'Do not attribute manually modified price to a merchant');
    assert.ok(!b.document.getElementById('results').classList.contains('visible'));
    const example = b.document.getElementById('example');
    example.click();
    assert.equal(source.hidden, true);
    assert.equal(b.document.getElementById('example-warning').hidden, false);

    const seller = b.document.querySelector('a[data-water-rakuten-offer]');
    assert.ok(seller.getAttribute('href').startsWith('https://hb.afl.rakuten.co.jp/'));
    assert.equal(seller.getAttribute('rel'), 'nofollow sponsored noopener');
    seller.addEventListener('click', ev => ev.preventDefault());
    seller.dispatchEvent(new b.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    const outgoing = b.events.filter(ev => ev[1] === 'affiliate_click' && ev[2].affiliate === 'rakuten');
    assert.equal(outgoing.length, 1);
    assert.equal(outgoing[0][2].click_position, 'water_cost_verified_offer');
    assert.equal(outgoing[0][2].operator_test, '1');
    assert.equal(outgoing[0][2].conversion_source, 'water_server_cost_comparison');
    assert.equal(outgoing[0][2].liters, undefined, 'Never send user water usage or price inputs to analytics');
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
