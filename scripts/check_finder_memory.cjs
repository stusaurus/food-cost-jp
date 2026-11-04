/* Real browser QA: explicit opt-in, returning to choices, and protected purchase links. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve('site'),OUT='finder-memory-evidence';
(async()=>{
  fs.mkdirSync(OUT,{recursive:true});
  const server=http.createServer((req,res)=>{
    const pathname=new URL(req.url,'http://localhost').pathname;
    let relative;
    try{relative=decodeURIComponent(pathname).replace(/^\/food-cost-jp\/?/, '')}catch(_){res.writeHead(400).end();return}
    let file=path.resolve(ROOT,relative);
    if(file!==ROOT&&!file.startsWith(ROOT+path.sep)){res.writeHead(403).end();return}
    if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');
    if(!fs.existsSync(file)){res.writeHead(404).end();return}
    const ext=path.extname(file);
    const types={'.html':'text/html; charset=utf-8','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg'};
    res.setHeader('Content-Type',types[ext]||'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch(),records=[],url='http://127.0.0.1:'+server.address().port+'/food-cost-jp/?test=1';
  try{
    for(const width of [320,390,1440]){
      const context=await browser.newContext({viewport:{width,height:900},locale:'ja-JP'});
      await context.route(/google-analytics\.com|googletagmanager\.com|analytics\.google\.com/,r=>r.abort());
      const page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      const response=await page.goto(url,{waitUntil:'domcontentloaded'});
      assert.equal(response.status(),200);
      assert.equal(await page.locator('#today-market .finder-product').count()>0,true,'products first');
      assert.equal(await page.locator('[data-finder-last-choice]').isVisible(),false);
      assert.equal(await page.evaluate(()=>localStorage.getItem('food_cost_finder_choice_v1')),null);
      await page.locator('[data-entry-route="known"]').click();
      await page.locator('[data-finder-category="rice"]').evaluate(e=>{e.closest('details').open=true});
      await page.locator('[data-finder-category="rice"]').click();
      assert.equal(await page.locator('[data-finder-picks="rice:cheap"]').isVisible(),true);
      assert.equal(await page.evaluate(()=>localStorage.getItem('food_cost_finder_choice_v1')),null,'no silent history recording');
      const items=page.locator('[data-finder-picks="rice:cheap"] [data-affiliate=rakuten]');
      assert(await items.count()>0);
      const href=await items.first().getAttribute('href');
      assert(/^https:\/\//.test(href),'purchase link remains an actual external https URL');
      await page.locator('[data-finder-remember]').click();
      const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('food_cost_finder_choice_v1')));
      assert.deepEqual(saved,{category:'rice',purpose:'cheap'});
      await page.reload({waitUntil:'domcontentloaded'});
      assert.equal(await page.locator('#today-market .finder-product').count()>0,true,'no takeover by remembered choice');
      assert.equal(await page.locator('[data-finder-last-choice]').isVisible(),true);
      assert.equal(await page.locator('[data-finder-route-stage]').isVisible(),true,'optional navigation is not forced open');
      await page.locator('[data-finder-resume]').click();
      assert.equal(await page.locator('[data-finder-picks="rice:cheap"]').isVisible(),true);
      assert.equal(await page.locator('[data-finder-remember]').getAttribute('aria-pressed'),'true');
      assert.equal(await page.locator('[data-finder-picks="rice:cheap"] [data-affiliate=rakuten]').first().getAttribute('href'),href);
      await page.locator('[data-finder-forget]').click();
      assert.equal(await page.evaluate(()=>localStorage.getItem('food_cost_finder_choice_v1')),null);
      assert.equal(await page.locator('[data-finder-last-choice]').isVisible(),false);
      assert.equal(await page.locator('[data-finder-picks="rice:cheap"]').isVisible(),true,'forgetting must not erase results');
      assert.equal(await page.locator('h1').count(),1);
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
      assert.equal(overflow,false,'horizontal overflow '+width);
      assert.deepEqual(errors,[]);
      await page.locator('#quick-finder').scrollIntoViewIfNeeded();
      await page.screenshot({path:OUT+'/finder-'+width+'.png',animations:'disabled'});
      records.push({width,productsFirst:true,explicitMemoryOnly:true,oneTapResume:true,forgetSafe:true,linkPreserved:true,overflow:false,errors:[]});
      await context.close();
    }
    fs.writeFileSync(OUT+'/report.json',JSON.stringify({results:records,affiliateNavigation:'blocked-by-test',checks:records.length},null,2));
    console.log(JSON.stringify(records));
  }finally{
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(e=>{console.error(e);process.exitCode=1});
