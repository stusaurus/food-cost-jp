// Real Chromium clicks at 320/390/1440px, with all external requests blocked.
// Never send affiliate clicks or the 1x1 impression pixel to A8 in QA.
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve('site');
const output='meal-budget-evidence';
const A8='https://px.a8.net/svt/ejp?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM';
const PIXEL='https://www19.a8.net/0.gif?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM';

(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const server=http.createServer((req,res)=>{
   const loc=new URL(req.url,'http://localhost');
   if(!loc.pathname.startsWith('/food-cost-jp/')){res.writeHead(404);res.end();return;}
   const rel=decodeURIComponent(loc.pathname.slice('/food-cost-jp/'.length));
   const file=path.resolve(root,rel.endsWith('/')?rel+'index.html':rel);
   if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
   res.setHeader('Content-Type',file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.js')?'application/javascript':'text/plain');
   res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true});
 const report=[];
 try {
  for(const width of [320,390,1440]){
   const context=await browser.newContext({viewport:{width,height:900},locale:'ja-JP'});
   await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
   const page=await context.newPage();
   const errors=[];
   page.on('pageerror',err=>errors.push(err.message));
   const url=origin+'/food-cost-jp/guides/family-meal-delivery-budget/?test=1';
   const response=await page.goto(url,{waitUntil:'networkidle'});
   assert.equal(response.status(),200);
   assert.equal(await page.locator('h1').count(),1);
   assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'),'https://stusaurus.github.io/food-cost-jp/guides/family-meal-delivery-budget/');
   const ad=page.locator('#chef-muten-ad');
   assert.equal(await ad.locator('a[href^="https://px.a8.net"]').getAttribute('href'),A8);
   assert.equal(await ad.locator('a[href^="https://px.a8.net"]').getAttribute('rel'),'nofollow');
   assert.equal(await ad.locator('img').getAttribute('src'),PIXEL);
   assert.match(await ad.innerText(),/広告｜A8.netアフィリエイト/);
   await page.locator('#meal-example').click();
   await page.locator('#meal-calculate').click();
   assert.equal(await page.locator('#meal-total').innerText(),'22,288円');
   assert.equal(await page.locator('#meal-per-dinner').innerText(),'2,786円');
   assert.equal(await page.locator('#meal-shipping-total').innerText(),'2,970円');
   await page.locator('#meal-deliveries').fill('2');
   await page.locator('#meal-calculate').click();
   assert.equal(await page.locator('#meal-total').innerText(),'9,962円');
   // Initial support plan: 3,799 + (5,173 + 990) = 9,962.
   await page.locator('#meal-plan').selectOption('omakase');
   await page.locator('#meal-example').click();
   await page.locator('#meal-deliveries').fill('4');
   await page.locator('#meal-calculate').click();
   assert.equal(await page.locator('#meal-total').innerText(),'53,771円');
   await page.locator('#meal-deliveries').fill('5');
   await page.locator('#meal-calculate').click();
   assert.equal(await page.locator('#meal-results').isVisible(),false);
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
   assert.equal(overflow,false,'horizontal overflow at '+width+'px');
   assert.deepEqual(errors,[]);
   await page.screenshot({path:output+'/family-meal-'+width+'.png',fullPage:true});
   report.push({viewport:width,service:'chef_muten',calculator:true,ad_creative:true,external_requests_blocked:true,overflow:false,errors});
   await context.close();
  }
  fs.writeFileSync(output+'/report.json',JSON.stringify({page:'/guides/family-meal-delivery-budget/',report},null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();server.close();}
})().catch(err=>{console.error(err);process.exitCode=1});
