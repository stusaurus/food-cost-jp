const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync(path.resolve(__dirname,'../assets/pack-rice-quantity-only.js'),'utf8');
const {countOnly}=require('../assets/pack-rice-quantity-only.js');

test('24-meal quantity-only calculator subtracts stock before boxes',()=>{
 assert.deepEqual(countOnly(1,30,0),{needed:30,shortage:30,boxes:2,leftover:18,noBuy:false});
 assert.deepEqual(countOnly(2,30,12),{needed:60,shortage:48,boxes:2,leftover:0,noBuy:false});
 assert.deepEqual(countOnly(2,30,60),{needed:60,shortage:0,boxes:0,leftover:0,noBuy:true});
 assert.deepEqual(countOnly(4,30,10),{needed:120,shortage:110,boxes:5,leftover:10,noBuy:false});
 for(const input of [[0,30,0],[25,30,0],[1,0,0],[1,91,0],[1,30,-1],[1,30,100001],[1.5,30,0],[1,30,NaN]]){
   assert.equal(countOnly(...input),null);
 }
});

function page(){
 const dom=new JSDOM(`<!doctype html><html><body><section data-rice-quantity-only>
 <form data-rice-quantity-form>
 <button type="button" data-rice-quantity-choice="1" aria-pressed="true"></button>
 <button type="button" data-rice-quantity-choice="2" aria-pressed="false"></button>
 <button type="button" data-rice-quantity-choice="3" aria-pressed="false"></button>
 <button type="button" data-rice-quantity-choice="4" aria-pressed="false"></button>
 <input data-rice-quantity-daily value="1">
 <input data-rice-quantity-days value="30">
 <input data-rice-quantity-stock value="0"></form>
 <p data-rice-quantity-error hidden></p>
 <div data-rice-quantity-result><p data-rice-quantity-summary></p>
 <span data-rice-quantity-needed></span><span data-rice-quantity-shortage></span>
 <span data-rice-quantity-boxes></span><span data-rice-quantity-leftover></span>
 </div></section></body></html>`,{
   url:'https://stusaurus.github.io/food-cost-jp/guides/pack-rice-24-servings-cost/',
   runScripts:'outside-only'
 });
 dom.window.eval(source);
 return dom;
}

test('quantity-only browser UI updates on chips, arbitrary manual input, stock and invalid input',()=>{
 const dom=page(),d=dom.window.document;
 const get=s=>d.querySelector('[data-rice-quantity-'+s+']');
 assert.equal(get('boxes').textContent,'2箱');
 get('choice="2"'); // no-op query is never a number or a purchase request
 d.querySelector('[data-rice-quantity-choice="2"]').click();
 assert.equal(get('daily').value,'2');
 assert.equal(get('boxes').textContent,'3箱');
 assert.equal(d.querySelector('[data-rice-quantity-choice="2"]').getAttribute('aria-pressed'),'true');
 get('stock').value='60';get('stock').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
 assert.equal(get('boxes').textContent,'0箱');
 assert.match(get('summary').textContent,/今は買い足し不要/);
 get('daily').value='5';get('daily').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
 assert.equal(get('boxes').textContent,'4箱');
 assert.ok([...d.querySelectorAll('[data-rice-quantity-choice]')].every(b=>b.getAttribute('aria-pressed')==='false'));
 get('daily').value='0';get('daily').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
 assert.equal(get('result').hidden,true);
 assert.equal(get('error').hidden,false);
 dom.window.close();
});

test('quantity-only JS never invents seller links, money or GA4 input telemetry',()=>{
 assert.doesNotMatch(source,/affiliate_click|data-affiliate|gtag\s*\(|sendBeacon|localStorage|fetch\s*\(|purchaseTotal|productUrl|楽天で購入/);
});
