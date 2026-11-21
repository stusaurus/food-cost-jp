const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const page = path.join(__dirname, '..', 'site', 'guides', 'rice-5kg-10kg-household-plan', 'index.html');

function boot() {
  const html = fs.readFileSync(page, 'utf8');
  const events = [];
  const dom = new JSDOM(html, {
    url: 'https://stusaurus.github.io/food-cost-jp/guides/rice-5kg-10kg-household-plan/?test=1',
    runScripts: 'dangerously',
    beforeParse(window) {
      window.gtag = (...args) => events.push(args);
    }
  });
  const doc = dom.window.document;
  return {
    dom, doc, events,
    get: id => doc.getElementById(id).textContent,
    change: (id, value) => {
      const input = doc.getElementById(id);
      input.value = String(value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles:true }));
    },
    calculate: () => doc.getElementById('calculate').click()
  };
}

test('2 go per day for 30 days requires 9kg dry rice and exact seller-sized orders', () => {
  const b = boot();
  try {
    const five = b.doc.querySelector('[data-rice-offer][data-kg="5"]');
    const ten = b.doc.querySelector('[data-rice-offer][data-kg="10"]');
    assert.ok(five && ten, 'The stored food snapshot must provide both exact bag sizes');
    const p5 = Number(five.dataset.price), p10 = Number(ten.dataset.price);
    assert.ok(Number.isInteger(p5) && p5 > 0);
    assert.ok(Number.isInteger(p10) && p10 > 0);
    assert.equal(b.get('required-kg'), '9kg');
    assert.equal(b.get('to-buy-kg'), '9kg');
    assert.equal(b.get('five-sets'), '5kgセット × 2');
    assert.equal(b.get('ten-sets'), '10kgセット × 1');
    assert.equal(b.get('five-total'), (p5 * 2).toLocaleString('ja-JP') + '円');
    assert.equal(b.get('ten-total'), p10.toLocaleString('ja-JP') + '円');
    assert.equal(b.get('five-leftover'), '見込み残量 1kg');
    assert.equal(b.get('ten-leftover'), '見込み残量 1kg');
    assert.equal(b.get('best-total'), Math.min(2 * p5,p10).toLocaleString('ja-JP') + '円');
    assert.equal(b.events.filter(e => e[1] === 'rice_household_plan').length, 0, 'Initial calculation is not an organic user action');
  } finally { b.dom.window.close(); }
});

test('30-day consumption can favor a 10kg+5kg combination; no inflated pack count', () => {
  const b = boot();
  try {
    const p5 = Number(b.doc.querySelector('[data-kg="5"]').dataset.price);
    const p10 = Number(b.doc.querySelector('[data-kg="10"]').dataset.price);
    b.change('go-day', 3);
    assert.equal(b.doc.getElementById('results').hidden, true, 'Changing an input invalidates old totals');
    b.calculate();
    assert.equal(b.get('required-kg'), '13.5kg');
    assert.equal(b.get('to-buy-kg'), '13.5kg');
    assert.equal(b.get('five-sets'), '5kgセット × 3');
    assert.equal(b.get('ten-sets'), '10kgセット × 2');
    assert.equal(b.get('best-total'), Math.min(3*p5,p10+p5,2*p10).toLocaleString('ja-JP') + '円');
    if (p10+p5 < Math.min(3*p5,2*p10)) {
      assert.equal(b.get('best-sets'), '5kgセット × 1、10kgセット × 1');
      assert.equal(b.get('best-leftover'), '見込み残量 1.5kg');
    }
    assert.equal(b.events.filter(e => e[1] === 'rice_household_plan').length, 1);
    const p=b.events.find(e=>e[1]==='rice_household_plan')[2];
    assert.equal(p.operator_test,'1');
    assert.equal(p['go-day'],undefined, 'Do not transmit household quantities into GA4');
    assert.equal(p.stock,undefined);
  } finally { b.dom.window.close(); }
});

test('stock can eliminate new purchasing; invalid decimal steps must not yield misleading results', () => {
  const b = boot();
  try {
    b.change('go-day',1);
    b.change('days',20);
    b.change('stock',5);
    b.calculate();
    assert.equal(b.get('required-kg'),'3kg');
    assert.equal(b.get('to-buy-kg'),'0kg');
    assert.equal(b.get('five-total'),'0円');
    assert.equal(b.get('ten-total'),'0円');
    assert.equal(b.get('best-total'),'0円');
    assert.equal(b.get('best-sets'),'5kgセット × 0、10kgセット × 0');
    assert.equal(b.get('best-leftover'),'見込み残量 2kg');
    b.change('go-day',2.05);
    b.calculate();
    assert.equal(b.doc.getElementById('results').hidden,true);
    assert.match(b.get('status'),/入力範囲内/);
    b.change('go-day',0.1);
    b.change('stock',0);
    b.change('days',1);
    b.calculate();
    assert.equal(b.get('required-kg'),'0.02kg');
    assert.equal(b.get('to-buy-kg'),'0.02kg');
  } finally { b.dom.window.close(); }
});

test('seller links are original, properly attributed, and do not leak input details', () => {
  const b=boot();
  try {
    const anchors=[...b.doc.querySelectorAll('a[data-affiliate="rakuten"]')];
    assert.equal(anchors.length,2);
    for(const a of anchors){
      assert.match(a.href,/^https:\/\/hb\.afl\.rakuten\.co\.jp\/hgc\//);
      assert.equal(a.target,'_blank');
      assert.equal(a.rel,'nofollow sponsored noopener');
      assert.equal(a.dataset.position,'rice_household_planner');
      assert.equal(a.dataset.metric,'per_kg');
      assert.equal(a.dataset.shipping,'included');
      assert.ok(a.dataset.productId);
      assert.ok(Number(a.dataset.unitPrice)>0);
    }
    anchors[0].addEventListener('click',e=>e.preventDefault());
    anchors[0].click();
    const outgoing=b.events.filter(e=>e[1]==='affiliate_click');
    assert.equal(outgoing.length,1);
    assert.equal(outgoing[0][2].operator_test,'1');
    assert.equal(outgoing[0][2].conversion_source,'rice_household_planner');
    assert.equal(outgoing[0][2].stock,undefined);
    assert.equal(outgoing[0][2].days,undefined);
    assert.equal(outgoing[0][2].daily_go,undefined);
  } finally { b.dom.window.close(); }
});
