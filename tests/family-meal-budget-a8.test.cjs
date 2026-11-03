const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const file = path.join(__dirname, '..', 'site', 'guides', 'family-meal-delivery-budget', 'index.html');
const href = 'https://px.a8.net/svt/ejp?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM';
const pixel = 'https://www19.a8.net/0.gif?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM';

function boot(query = '?test=1') {
  const events = [];
  const dom = new JSDOM(fs.readFileSync(file,'utf8'), {
    url: 'https://stusaurus.github.io/food-cost-jp/guides/family-meal-delivery-budget/' + query,
    runScripts: 'dangerously',
    beforeParse(window) { window.gtag = (...args) => events.push(args); }
  });
  const d = dom.window.document;
  const fill = (id,v) => {d.getElementById(id).value = String(v);};
  const click = id => {d.getElementById(id).click();};
  const text = id => d.getElementById(id).textContent;
  return {dom, events, d, fill, click, text};
}

test('official A8 ad is clearly disclosed and click+pixel remain exactly provided', () => {
  const b=boot();
  try {
    const card=b.d.querySelector('#chef-muten-ad');
    assert.ok(card);
    assert.match(card.textContent,/広告｜A8.netアフィリエイト/);
    assert.match(card.textContent,/広告主提供の表現/);
    const a=card.querySelector('a');
    const img=card.querySelector('img');
    assert.equal(a.getAttribute('href'),href);
    assert.equal(a.getAttribute('rel'),'nofollow');
    assert.equal(a.textContent,'お子様にも安心！"添加物不使用"のつくりおきおかず');
    assert.equal(img.getAttribute('src'),pixel);
    assert.equal(img.getAttribute('width'),'1');
    assert.equal(img.getAttribute('height'),'1');
    assert.equal(b.d.querySelectorAll('a[href^="https://px.a8.net"]').length,1);
    a.addEventListener('click',e=>e.preventDefault());
    a.dispatchEvent(new b.dom.window.MouseEvent('click',{bubbles:true,cancelable:true}));
    const hits=b.events.filter(e=>e[0]==='event'&&e[1]==='affiliate_click');
    assert.equal(hits.length,1);
    assert.equal(hits[0][2].affiliate,'a8');
    assert.equal(hits[0][2].program,'chef_muten_tsukurioki');
    assert.equal(hits[0][2].site_id,'food_cost_jp');
    assert.equal(hits[0][2].operator_test,'1');
    assert.equal(hits[0][2].conversion_source,'family_meal_budget_planner');
    assert.equal(a.getAttribute('href'),href);
  } finally {b.dom.window.close();}
});

test('4-week fees include first discount and each later delivery shipping, not just advertised one-off price', () => {
  const b=boot();
  try {
    b.click('meal-example');
    b.click('meal-calculate');
    assert.equal(b.d.getElementById('meal-results').hidden,false);
    assert.equal(b.text('meal-total'),'22,288円');
    assert.equal(b.text('meal-per-dinner'),'2,786円');
    assert.equal(b.text('meal-orders'),'4回（初回 1回・通常 3回）');
    assert.equal(b.text('meal-product-total'),'19,318円');
    assert.equal(b.text('meal-shipping-total'),'2,970円');
    assert.equal(b.text('meal-dinners'),'8回相当');
    assert.equal(b.events.filter(e=>e[1]==='meal_budget_calculate').length,1);
    const ev=b.events.find(e=>e[1]==='meal_budget_calculate')[2];
    assert.equal(ev.operator_test,'1');
    assert.equal(ev.order_price,undefined);
    assert.equal(ev.household_size,undefined);

    b.d.getElementById('meal-include-first').checked=false;
    b.click('meal-calculate');
    assert.equal(b.text('meal-total'),'24,652円');
    assert.equal(b.text('meal-shipping-total'),'3,960円');
    assert.equal(b.text('meal-per-dinner'),'3,082円');

    b.fill('meal-deliveries',0);
    b.click('meal-calculate');
    assert.equal(b.text('meal-total'),'0円');
    assert.equal(b.text('meal-per-dinner'),'―');
    assert.match(b.text('meal-verdict'),/費用が発生する場合/);
  } finally {b.dom.window.close();}
});

test('omakase plan separately calculates 4-week family dinner cost and lets families skip deliveries', () => {
  const b=boot('?test=0');
  try {
    b.fill('meal-plan','omakase');
    b.click('meal-example');
    b.click('meal-calculate');
    assert.equal(b.text('meal-total'),'53,771円');
    assert.equal(b.text('meal-per-dinner'),'4,481円');
    assert.equal(b.text('meal-dinners'),'12回相当');
    b.fill('meal-deliveries',2);
    b.click('meal-calculate');
    assert.equal(b.text('meal-total'),'24,577円');
    assert.equal(b.text('meal-dinners'),'6回相当');
    assert.equal(b.events.filter(e=>e[1]==='meal_budget_calculate')[0][2].operator_test,'0');
  } finally {b.dom.window.close();}
});

test('invalid or missing prices never result in fictional checkout totals', () => {
  const b=boot();
  try {
    b.click('meal-calculate');
    assert.equal(b.d.getElementById('meal-results').hidden,true);
    assert.match(b.text('meal-error'),/すべての欄/);
    b.click('meal-example');
    b.fill('meal-deliveries',5);
    b.click('meal-calculate');
    assert.equal(b.d.getElementById('meal-results').hidden,true);
    assert.match(b.text('meal-error'),/配送回数/);
    b.fill('meal-deliveries',4);
    b.fill('meal-regular-shipping',-1);
    b.click('meal-calculate');
    assert.equal(b.d.getElementById('meal-results').hidden,true);
    b.fill('meal-regular-shipping',990);
    b.click('meal-calculate');
    assert.equal(b.d.getElementById('meal-results').hidden,false);
  } finally {b.dom.window.close();}
});

test('new guide is reachable from home without altering existing water A8 creative',()=>{
  const home=fs.readFileSync('site/index.html','utf8');
  const water=fs.readFileSync('site/guides/water-server-vs-bottled-water/index.html','utf8');
  const sitemap=fs.readFileSync('site/sitemap.xml','utf8');
  assert.equal(home.split('family-meal-delivery-budget/').length-1,1);
  assert.ok(home.includes('family-meal-budget-entry'));
  assert.equal(sitemap.split('family-meal-delivery-budget/').length-1,1);
  assert.ok(water.includes('a8mat=4BGCF1+53DLEY+2B8Y+15OK2A'));
  assert.ok(!water.includes('4BGCF1+8J7R8Q+57YO+5YJRM'));
});
