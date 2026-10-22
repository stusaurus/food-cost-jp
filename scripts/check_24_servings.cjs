const fs=require('node:fs'),http=require('node:http'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const output='pack-size-evidence', root=path.resolve('site');
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const snapshot=JSON.parse(fs.readFileSync('site/data/products.json'));
 const expected=snapshot.categories['pack-rice'].included.filter(x=>x.quantity.count===24).sort((a,b)=>a.unit_prices.per_serving-b.unit_prices.per_serving||a.price-b.price).slice(0,3);
 assert(expected.length>=3);
 const server=http.createServer((req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname.replace(/^\/food-cost-jp\//,'');
  const file=path.resolve(root,pathname)+(pathname.endsWith('/')?'index.html':'');
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.svg')?'image/svg+xml':'image/webp');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url='http://127.0.0.1:'+server.address().port+'/food-cost-jp/guides/pack-rice-24-servings-cost/';
 const browser=await chromium.launch();const results=[];
 try{
  for(const width of [320,390,1440]){
   const context=await browser.newContext({viewport:{width,height:900},locale:'ja-JP'});
   await context.route(/google-analytics\.com|googletagmanager\.com|analytics\.google\.com/,r=>r.abort());
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto(url+'?test=1',{waitUntil:'networkidle'});assert.equal(response.status(),200);
   const cards=page.locator('.podium-card');assert.equal(await cards.count(),3);
   const canonical=await page.locator('link[rel=canonical]').getAttribute('href');assert.equal(canonical,'https://stusaurus.github.io/food-cost-jp/guides/pack-rice-24-servings-cost/');
   for(let i=0;i<3;i++){
    const text=await cards.nth(i).locator('.podium-size-comparison').innerText();
    assert(text.includes('1食 '+expected[i].quantity.unit_weight_g+'g'));
    const anchor=cards.nth(i).locator('a[data-affiliate=rakuten]');
    assert.equal(await anchor.getAttribute('href'),expected[i].url);
    assert((await anchor.getAttribute('rel')).includes('sponsored'));
   }
   assert.equal(await page.locator('h1').count(),1);
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);assert(!overflow);assert.deepEqual(errors,[]);
   await cards.first().scrollIntoViewIfNeeded();await page.screenshot({path:output+'/'+width+'.png'});
   results.push({width,status:200,overflow,errors,cards:3,canonical,purchaseLinksUnchanged:true});await context.close();
  }
  const {default:lighthouse}=await import(process.env.LIGHTHOUSE_MODULE||'lighthouse');
  const {launch}=await import(process.env.CHROME_LAUNCHER_MODULE||'chrome-launcher');
  const chrome=await launch({chromePath:chromium.executablePath(),chromeFlags:['--headless','--no-sandbox']});
  try{
   for(const mode of ['mobile','desktop']){
    const settings=mode==='desktop'?{formFactor:'desktop',screenEmulation:{mobile:false,width:1440,height:900,deviceScaleFactor:1,disabled:false}}:{};
    const r=await lighthouse(url+'?test=1',{port:chrome.port,logLevel:'error',output:'json',onlyCategories:['performance','accessibility','best-practices','seo'],blockedUrlPatterns:['*google-analytics.com*','*googletagmanager.com*'],...settings});
    fs.writeFileSync(output+'/lighthouse-'+mode+'.json',r.report);
    results.push({lighthouse:mode,scores:Object.fromEntries(Object.entries(r.lhr.categories).map(([k,v])=>[k,v.score]))});assert(r.lhr.categories.seo.score>=.9);assert(r.lhr.categories.accessibility.score>=.9);
   }
  }finally{await chrome.kill();}
  fs.writeFileSync(output+'/report.json',JSON.stringify({snapshotGeneratedAt:snapshot.generated_at,results},null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
