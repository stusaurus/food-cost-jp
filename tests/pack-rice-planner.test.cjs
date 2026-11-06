const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const file = path.join(__dirname, '..', 'assets', 'pack-rice-planner.js');
const js = fs.readFileSync(file, 'utf8');
const { calculate, calculateWithStock } = require(file);

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
    '<div class="rice-meal-choices">',
    '<button type="button" data-rice-meal-choice="1" aria-pressed="true">1食</button>',
    '<button type="button" data-rice-meal-choice="2" aria-pressed="false">2食</button>',
    '<button type="button" data-rice-meal-choice="3" aria-pressed="false">3食</button>',
    '<button type="button" data-rice-meal-choice="4" aria-pressed="false">4食</button>',
    '</div>',
    '<input id="rice-meals-day" type="number" value="1">',
    '<input data-rice-stock-input type="number" value="0">',
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
    '<span data-rice-shortage></span><p data-rice-recommendation></p>',
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

test('stock subtracts before box rounding without altering legacy math', () => {
  const noBuy = calculateWithStock(24, 3600, 1, 30);
  assert.equal(noBuy.shortage, 0);
  assert.equal(noBuy.boxes, 0);
  assert.equal(noBuy.purchaseTotal, 0);
  assert.equal(noBuy.remainingMeals, 0);
  assert.equal(noBuy.noBuy, true);
  const shortage = calculateWithStock(24, 3600, 1, 10);
  assert.equal(shortage.shortage, 20);
  assert.equal(shortage.boxes, 1);
  assert.equal(shortage.purchaseTotal, 3600);
  assert.equal(shortage.remainingMeals, 4);
  assert.equal(shortage.consumptionCost, 3000);
  for (const stock of [-1, 1.5, NaN, 100001, Infinity]) {
    assert.equal(calculateWithStock(24, 3600, 1, stock), null);
  }
  assert.equal(calculateWithStock(24, -1, 1, 30), null);
});

test('stock field changes visible recommendation and hides buy CTA only when no purchase is needed', () => {
  const { dom, events } = page();
  const doc = dom.window.document;
  const get = name => doc.querySelector('[data-rice-' + name + ']').textContent;
  const shop = doc.querySelector('[data-rice-planner-buy]');
  assert.equal(shop.hidden, false);
  assert.equal(get('shortage'), '30食');
  const stock = doc.querySelector('[data-rice-stock-input]');
  stock.value = '30';
  stock.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(get('boxes'), '0箱');
  assert.equal(get('purchase'), '¥0');
  assert.equal(get('shortage'), '0食');
  assert.match(get('recommendation'), /今は買い足し不要/);
  assert.equal(shop.hidden, true);
  stock.value = '10';
  stock.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(get('boxes'), '1箱');
  assert.equal(get('purchase'), '¥3,600');
  assert.equal(get('leftover'), '4食');
  assert.equal(shop.hidden, false);
  stock.value = '-1';
  stock.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  assert.equal(doc.querySelector('[data-rice-planner-results]').hidden, true);
  assert.equal(shop.hidden, true); // Never expose a stale purchase CTA after invalid input.
  assert.equal(events.length, 0); // Input values are never sent to analytics.
  dom.window.close();
});

test('one-tap daily meal choices recalculate boxes, sync pressed state and respect no-buy stock', () => {
  const { dom, events } = page();
  const doc = dom.window.document;
  const chip = n => doc.querySelector('[data-rice-meal-choice="'+n+'"]');
  const field = doc.querySelector('#rice-meals-day');
  const stock = doc.querySelector('[data-rice-stock-input]');
  const get = name => doc.querySelector('[data-rice-' + name + ']').textContent;
  assert.equal(chip(1).getAttribute('aria-pressed'), 'true');
  chip(2).click();
  assert.equal(field.value,'2');
  assert.equal(chip(2).getAttribute('aria-pressed'),'true');
  assert.equal(chip(1).getAttribute('aria-pressed'),'false');
  assert.equal(get('boxes'), '3箱');
  assert.equal(get('purchase'), '¥10,800');
  stock.value='60';
  stock.dispatchEvent(new dom.window.Event('input', {bubbles:true}));
  assert.equal(get('boxes'),'0箱');
  assert.equal(get('purchase'),'¥0');
  assert.match(get('recommendation'),/今は買い足し不要/);
  assert.equal(doc.querySelector('[data-rice-planner-buy]').hidden,true);
  chip(4).click();
  assert.equal(field.value,'4');
  assert.equal(get('boxes'),'3箱');
  assert.equal(chip(4).getAttribute('aria-pressed'),'true');
  field.value='5';
  field.dispatchEvent(new dom.window.Event('input', {bubbles:true}));
  assert.ok([...doc.querySelectorAll('[data-rice-meal-choice]')].every(
    button=>button.getAttribute('aria-pressed')==='false'));
  // Analytics never transmit food usage or household inventory counts.
  assert.ok(events.every(e=>e.info.meals_per_day===undefined &&
    e.info.stock_meals===undefined));
  dom.window.close();
});
