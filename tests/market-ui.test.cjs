const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('site/index.html','utf8').replace(/<script\b[^>]*src=[^>]*>[\s\S]*?<\/script>/gi,'');
function boot(html=source,url='https://stusaurus.github.io/food-cost-jp/?test=1'){
 const events=[];
 const dom=new JSDOM(html,{url,runScripts:'dangerously',beforeParse(w){w.gtag=(...args)=>events.push(args);}});
 const d=dom.window.document;
 return {dom,d,events,click:s=>{assert.ok(d.querySelector(s),s);d.querySelector(s).click()},visible:s=>!d.querySelector(s).closest('[hidden]')};
}
test('all five shopping intents open cross-category shelves without a food question',()=>{
 for(const intent of ['cheap','large','small','budget','storage']){
  const b=boot();assert.ok(b.visible('[data-finder-route-stage]'));assert.ok(!b.visible('[data-finder-purpose-stage]'));assert.ok(!b.visible('[data-finder-category-stage]'));
  b.click(intent==='cheap'?'[data-entry-route="deal"]':'[data-entry-route="advisor"]');
  if(intent!=='cheap'){assert.ok(b.visible('[data-finder-purpose-stage]'));b.click(`[data-finder-purpose="${intent}"]`)}
  assert.ok(!b.visible('[data-finder-category-stage]'));
  assert.ok(b.visible(`[data-finder-picks="all:${intent}"]`));
  const e=b.events.find(e=>e[1]==='finder_complete');assert.equal(e[2].shopping_intent,intent);assert.equal(e[2].category_id,'all');assert.equal(e[2].operator_test,'1');
  b.click('[data-finder-narrow]');assert.ok(b.visible('[data-finder-category-stage]'));
  b.click('[data-finder-category="rice"]');assert.ok(b.visible(`[data-finder-picks="rice:${intent}"]`));
  b.click('[data-finder-reset]');assert.ok(b.visible('[data-finder-route-stage]'));assert.ok(!b.visible('[data-finder-result-stage]'));b.dom.window.close();
 }
});
test('known food asks the category only after intent; all four categories work',()=>{
 for(const category of ['pack-rice','rice','carbonated-water','oatmeal']){
  const b=boot();b.click('[data-entry-route="known"]');assert.ok(b.visible('[data-finder-category-stage]'));assert.ok(!b.visible('[data-finder-result-stage]'));
  b.click(`[data-finder-category="${category}"]`);assert.ok(b.visible(`[data-finder-picks="${category}:cheap"]`));
  assert.equal(b.events.find(e=>e[1]==='category_select_after_intent')[2].shopping_intent,'known');b.dom.window.close();
 }
});
test('save storage and same-category comparison contract survive cross-category discovery',()=>{
 const b=boot(),shelf=b.d.querySelector('[data-market-shelf="today"]');
 const saves=shelf.querySelectorAll('[data-save-product]'),compares=shelf.querySelectorAll('[data-compare-product]');
 saves[0].click();assert.equal(JSON.parse(b.dom.window.localStorage.getItem('food_cost_saved_v1')).length,1);
 compares[0].click();compares[1].click();assert.equal(JSON.parse(b.dom.window.localStorage.getItem('food_cost_compare_v1')).length,1);
 assert.ok(!b.d.querySelector('[data-compare-bar]').hidden);
 saves[0].click();assert.equal(JSON.parse(b.dom.window.localStorage.getItem('food_cost_saved_v1')).length,0);b.dom.window.close();
});
test('shelf and affiliate click events coexist with existing conversion tracking',()=>{
 const b=boot();b.click('[data-entry-route="deal"]');
 const a=b.d.querySelector('[data-finder-picks="all:cheap"] [data-affiliate]');
 a.addEventListener('click',e=>e.preventDefault());a.click();
 for(const n of ['shopping_intent_select','finder_complete','quick_finder_complete','market_shelf_view','market_shelf_product_click','affiliate_click','product_result_click'])assert.ok(b.events.some(e=>e[1]===n),n);
 const affiliate=b.events.find(e=>e[1]==='affiliate_click');assert.ok(affiliate[2].cta_variant);assert.equal(affiliate[2].shipping_status,'included');b.dom.window.close();
});
test('price history 7 / 30 days remains interactive',()=>{
 const b=boot();const button=b.d.querySelector('[data-market-shelf="today"] [data-history-range="30日"]');assert.ok(button);button.click();assert.ok(button.classList.contains('selected'));assert.ok(b.events.some(e=>e[1]==='price_history_range_change'));b.dom.window.close();
});

test('carbonated stock landing and later filtering consistently use total volume',()=>{
 const html=fs.readFileSync('site/categories/carbonated-water/index.html','utf8').replace(/<script\b[^>]*src=[^>]*>[\s\S]*?<\/script>/gi,'');
 const b=boot(html,'https://stusaurus.github.io/food-cost-jp/categories/carbonated-water/?pick=large');
 const root=b.d.querySelector('[data-comparison]'),filter=root.querySelector('[data-filter]');
 assert.equal(filter.querySelector('[value=large]').textContent,'合計12L超');
 for(const row of root.querySelectorAll('tbody tr'))assert.equal(row.hidden,row.dataset.shoppingBucket!=='large');
 filter.value='small';filter.dispatchEvent(new b.dom.window.Event('change'));
 for(const row of root.querySelectorAll('tbody tr'))assert.equal(row.hidden,row.dataset.shoppingBucket!=='small');
 b.dom.window.close();
});

test('three routes, progressive disclosure, hero CTA and route events',()=>{
 const b=boot();assert.equal(b.d.querySelectorAll('[data-entry-route]').length,3);
 assert.ok(!b.visible('[data-finder-purpose-stage]'));assert.ok(!b.visible('[data-finder-category-stage]'));
 b.click('[data-entry-route="advisor"]');assert.ok(b.visible('[data-finder-purpose-stage]'));
 assert.equal(b.d.querySelectorAll('[data-finder-purpose]').length,4);
 assert.equal(b.events.find(e=>e[1]==='entry_route_select')[2].entry_route,'advisor');
 b.click('[data-hero-primary]');assert.ok(b.visible('[data-finder-purpose-stage]'));assert.ok(!b.visible('[data-finder-route-stage]'));assert.equal(b.events.find(e=>e[1]==='hero_primary_cta')[2].entry_route,'advisor');assert.equal(b.events.filter(e=>e[1]==='entry_route_select').at(-1)[2].entry_source,'hero');
 b.click('[data-hero-known]');assert.ok(b.visible('[data-finder-category-stage]'));assert.equal(b.events.filter(e=>e[1]==='entry_route_select').at(-1)[2].entry_route,'known');b.dom.window.close();
});

test('high-resolution discovery images fall back once to the API URL',()=>{
 const b=boot();const img=b.d.querySelector('img[data-image-fallback]');assert.ok(img);const original=img.dataset.imageFallback;
 img.dispatchEvent(new b.dom.window.Event('error'));assert.equal(img.src,original);assert.ok(!img.dataset.imageFallback);
 img.dispatchEvent(new b.dom.window.Event('error'));assert.equal(img.src,original);b.dom.window.close();
});
