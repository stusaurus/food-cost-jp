const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const file = path.join(__dirname, '..', 'assets', 'pack-rice-planner.js');
const js = fs.readFileSync(file, 'utf8');
const { calculate } = require(file);

test('24 meals x one/day and two/day have exact days, cash and leftovers', () => {
  assert.deepEqual(calculate(24, 3600, 1), {
    daysPerBox: 24, mealsNeeded: 30, boxes: 2, purchaseTotal: 7200,
    remainingMeals: 18, oneMealPrice: 150, consumptionCost: 4500
  });
  assert.equal(calculate(24, 3600, 2).daysPerBox, 12);
  assert.equal(calculate(24, 3600, 2).boxes, 3);
  assert.equal(calculate(24, 3600, 2).remainingMeals, 12);
  assert.equal(calculate(24, 3600, 0), null);
  assert.equal(calculate(24, 3600, 25), null);
  assert.equal(calculate(24, -1, 1), null);
  assert.equal(calculate(0, 3600, 1), null);
  assert.equal(calculate(24, 3600, 1.5), null);
});

function page() {
  const markup = [
    '<!doctype html><html><body><section data-rice-planner>',
    '<form data-rice-planner-form>',
    '<input id="rice-meals-day" type="number" value="1">',
    '<select data-rice-planner-product>',
    '<option value="0" data-count="24" data-price="3600" data-grams="180"',
    ' data-product-id="shop:item1" data-product-name="1番" data-product-url="https://item.rakuten.co.jp/a/1/"',
    ' data-rank="1" data-unit-price="150.000000">1番</option>',
    '<option value="1" data-count="24" data-price="4800" data-grams="200"',
    ' data-product-id="shop:item2" data-product-name="2番" data-product-url="https://item.rakuten.co.jp/b/2/"',
    ' data-rank="2" data-unit-price="200.000000">2番</option>',
    '</select></form><p data-rice-planner-error hidden></p>',
    '<div data-rice-planner-results>',
    '<span data-rice-days></span><span data-rice-boxes></span>',
    '<span data-rice-purchase></span><span data-rice-leftover></span>',
    '<span data-rice-unit></span><p data-rice-detail></p>',
    '<a data-rice-planner-buy href="https://item.rakuten.co.jp/a/1/" data-affiliate="rakuten"></a>',
    '</div></section></body></html>'
  ].join('');
  const dom = new JSDOM(markup, {
    url: 'https://stusaurus.github.io/food-cost-jp/guides/pack-rice-24-servings-cost/',
    runScripts: 'outside-only'
  });
  const events = [];
  dom.window.foodCostTrack = (name, info) => events.push({ name, info });
  dom.window.eval(js);
  return { dom, events };
}

test('rendered form recalculates on usage and selected actual product', () => {
  const { dom, events } = page();
  const doc = dom.window.document;
  const input = doc.querySelector('#rice-meals-day');
  const select = doc.querySelector('[data-rice-planner-product]');
  const get = attr => doc.querySelector('[data-rice-' + attr + ']').textContent;
  assert.equal(get('days'), '24日');
  assert.equal(get('boxes'), '2箱');
  assert.equal(get('purchase'), '¥7,200');
  assert.equal(get('leftover'), '18食');
  input.value = '2';
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(get('days'), '12日');
  assert.equal(get('boxes'), '3箱');
  assert.equal(get('purchase'), '¥10,800');
  assert.equal(get('leftover'), '12食');
  select.value = '1';
  select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  assert.equal(get('purchase'), '¥14,400');
  assert.equal(get('unit'), '¥200');
  assert.match(get('detail'), /1食 200g/);
  const shop = doc.querySelector('[data-rice-planner-buy]');
  assert.equal(shop.href, 'https://item.rakuten.co.jp/b/2/');
  assert.equal(shop.dataset.productId, 'shop:item2');
  assert.equal(shop.dataset.rank, '2');
  assert.equal(shop.dataset.unitPrice, '200.000000');
  assert.equal(events.length, 1);
  assert.equal(events[0].name, 'usage_planner_use');
  assert.equal(events[0].info.product_id, 'shop:item2');
  assert.equal(events[0].info.meals_per_day, undefined);
  input.value = '0';
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(doc.querySelector('[data-rice-planner-results]').hidden, true);
  assert.equal(doc.querySelector('[data-rice-planner-error]').hidden, false);
  assert.equal(events.length, 1);
});

test('invalid user input never produces an unverified affiliate link', () => {
  const { dom } = page();
  const doc = dom.window.document;
  const select = doc.querySelector('[data-rice-planner-product]');
  select.selectedOptions[0].dataset.productUrl = 'https://example.com/not-merchant';
  select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  assert.equal(doc.querySelector('[data-rice-planner-results]').hidden, true);
  assert.equal(doc.querySelector('[data-rice-planner-error]').hidden, false);
});
