const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('site/index.html','utf8').replace(/<script\b[^>]*src=[^>]*>[\s\S]*?<\/script>/gi,'');
function boot(html=source,url='https://stusaurus.github.io/food-cost-jp/?test=1'){
 const events=[];
 const instrumented=html.replace('</head>', '<script>window.gtag=(...args)=>window.__testEvents.push(args);</script></head>');
 const dom=new JSDOM(instrumented,{url,runScripts:'dangerously',beforeParse(w){w.__testEvents=events;w.scrollTo=()=>{};w.gtag=(...args)=>events.push(args);}});
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

test('all eligible categories are grouped by department and complete Finder with their own IDs',()=>{
 const data=JSON.parse(fs.readFileSync('site/data/products.json','utf8'));
 const legacy=['pack-rice','rice','carbonated-water','oatmeal'];
 const eligible=Object.entries(data.categories).filter(([id,v])=>legacy.includes(id)||v.included.length>=3).map(([id])=>id);
 const b=boot();b.click('[data-entry-route="known"]');
 assert.ok(b.d.querySelectorAll('.finder-aisle').length>=3);
 assert.equal(b.d.querySelectorAll('[data-finder-category]').length,eligible.length);
 assert.equal(b.d.querySelectorAll('[data-aisle-category]').length,eligible.length);
 for(const id of eligible){
  b.click('[data-finder-reset]');b.click('[data-entry-route="known"]');
  const button=b.d.querySelector(`[data-finder-category="${id}"]`);
  assert.ok(button.closest('.finder-aisle'));
  button.closest('details').open=true;button.click();
  assert.ok(b.visible(`[data-finder-picks="${id}:cheap"]`));
  const event=b.events.filter(e=>e[1]==='finder_complete').at(-1);assert.equal(event[2].category_id,id);
  const link=b.d.querySelector(`[data-finder-picks="${id}:cheap"] [data-affiliate]`);
  if(link){link.addEventListener('click',e=>e.preventDefault());link.click();assert.equal(b.events.filter(e=>e[1]==='affiliate_click').at(-1)[2].category_id,id)}
 }
 b.dom.window.close();
});

test('new category save, comparison and history links retain category-specific units',()=>{
 const b=boot();
 for(const id of ['mineral-water','pasta','granola','retort-curry','bag-noodles','cup-noodles']){
  const panel=b.d.querySelector(`[data-finder-picks="${id}:cheap"]`);if(!panel)continue;
  const saves=panel.querySelectorAll('[data-save-product]'),compares=panel.querySelectorAll('[data-compare-product]');
  if(!saves.length)continue;
  saves[0].click();const saved=JSON.parse(b.dom.window.localStorage.getItem('food_cost_saved_v1')).find(x=>x.category===id);assert.equal(saved.category,id);assert.ok(saved.unit>0);assert.ok(saved.unitLabel);
  compares[0].click();if(compares.length>1)compares[1].click();
  const compared=JSON.parse(b.dom.window.localStorage.getItem('food_cost_compare_v1'));assert.ok(compared.every(x=>x.category===id));
  assert.equal(b.events.filter(e=>e[1]==='product_save_toggle').at(-1)[2].category_id,id);
  b.click('[data-clear-compare]');
 }
 b.dom.window.close();
});

test('saved and comparison modal affiliate clicks retain complete attribution',()=>{
 const b=boot(),panel=b.d.querySelector('[data-finder-picks="rice:cheap"]');
 panel.querySelector('[data-save-product]').click();panel.querySelector('[data-compare-product]').click();
 for(const [open,link,source] of [['[data-open-saved]','[data-saved-list] [data-affiliate]','saved_modal'],['[data-open-compare]','[data-compare-table] [data-affiliate]','compare_modal']]){
  b.click(open);const a=b.d.querySelector(link);assert.ok(a);a.addEventListener('click',e=>e.preventDefault());a.click();
  const x=b.events.filter(e=>e[1]==='affiliate_click').at(-1)[2];
  assert.equal(x.conversion_source,source);assert.equal(x.category_id,'rice');assert.equal(x.operator_test,'1');assert.equal(x.comparison_metric,'per_kg');assert.equal(x.shipping_status,'included');assert.ok(x.rank);assert.ok(x.unit_price>0);
 }
 b.dom.window.close();
});

test('operator flag is set before GA config, reset works and storage errors are safe',()=>{
 for(const flag of ['1','0']){
  const b=boot(source,'https://stusaurus.github.io/food-cost-jp/?test='+flag);
  const config=b.events.find(e=>e[0]==='config');assert.ok(config,'snapshot must render with GA measurement ID');assert.equal(config[2].operator_test,flag);
  assert.ok(!b.dom.window.location.search.includes('test='));b.dom.window.close();
 }
 const events=[];
 const dom=new JSDOM(source,{url:'https://stusaurus.github.io/food-cost-jp/?test=1',runScripts:'dangerously',beforeParse(w){w.gtag=(...args)=>events.push(args);Object.defineProperty(w,'localStorage',{get(){throw Error('denied')}})}});
 assert.equal(events.find(e=>e[0]==='config')[2].operator_test,'1');dom.window.close();
});

test('saved watch uses latest prices, tracks affiliate clicks, and hides unavailable offers',async()=>{
 const data=JSON.parse(fs.readFileSync('site/data/products.json','utf8')),live=data.categories.rice.included[0],events=[];
 const stored=[{id:live.id,name:'Old price',category:'rice',price:1,unit:1},{id:'missing:item',name:'Missing',category:'rice',price:1}];
 const html=fs.readFileSync('site/saved/index.html','utf8').replace(/<script\b[^>]*src=[^>]*>[\s\S]*?<\/script>/gi,'');
 const dom=new JSDOM(html,{url:'https://stusaurus.github.io/food-cost-jp/saved/?test=1',runScripts:'dangerously',beforeParse(w){w.localStorage.setItem('food_cost_saved_v1',JSON.stringify(stored));w.gtag=(...args)=>events.push(args);w.fetch=async()=>({ok:true,json:async()=>data})}});
 await new Promise(resolve=>setImmediate(resolve));const d=dom.window.document;
 const links=d.querySelectorAll('[data-watch-list] [data-affiliate]');assert.equal(links.length,1);assert.equal(links[0].dataset.productId,live.id);
 assert.ok(d.querySelector('[data-watch-list]').textContent.includes(live.price.toLocaleString('ja-JP')));
 links[0].addEventListener('click',e=>e.preventDefault());links[0].click();
 const x=events.find(e=>e[1]==='affiliate_click')[2];assert.equal(x.conversion_source,'saved_watch');assert.equal(x.operator_test,'1');assert.equal(x.category_id,'rice');
 assert.equal(d.querySelectorAll('.unavailable [data-affiliate]').length,0);dom.window.close();
});

test('old comparison entries refresh quantity, unit, shipping and price from current data',async()=>{
 const data=JSON.parse(fs.readFileSync('site/data/products.json','utf8')),x=data.categories.rice.included[0];
 const original=JSON.parse(JSON.stringify(data));original.categories.rice.included[0]={...x,price:x.price+100,quantity_label:'更新後の容量',shipping_status:'extra_or_unknown'};
 const dom=new JSDOM(source,{url:'https://stusaurus.github.io/food-cost-jp/?test=1',runScripts:'dangerously',beforeParse(w){w.localStorage.setItem('food_cost_compare_v1',JSON.stringify([{id:x.id,category:'rice',price:1,unit:1,quantity:'old'}]));w.fetch=async()=>({ok:true,json:async()=>original})}});
 await new Promise(resolve=>setImmediate(resolve));const stored=JSON.parse(dom.window.localStorage.getItem('food_cost_compare_v1'))[0];
 assert.equal(stored.price,x.price+100);assert.equal(stored.quantity,'更新後の容量');assert.equal(stored.shipping,'extra_or_unknown');assert.equal(stored.verified,true);dom.window.close();
});
