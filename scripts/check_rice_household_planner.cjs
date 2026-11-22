// Browser QA for both real-data and missing-price rice calculators, across viewport sizes.
// All third-party requests are blocked; do not click live affiliate links.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve('site'), output = 'rice-household-evidence';
const route = '/food-cost-jp/guides/rice-5kg-10kg-household-plan/';
const guide = path.join(root, 'guides/rice-5kg-10kg-household-plan');
(async () => {
  fs.mkdirSync(output, {recursive: true});
  const fallback = execFileSync('python', ['-c',
    'from scripts.rice_household_planner import page; print(page([], checked_at=None))'
  ], {encoding:'utf8'});
  fs.writeFileSync(path.join(guide, 'fallback-qa.html'), fallback);
  const server = http.createServer((req,res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    if (!pathname.startsWith('/food-cost-jp/')) { res.writeHead(404);res.end();return; }
    const rel = decodeURIComponent(pathname.slice('/food-cost-jp/'.length));
    const file = path.resolve(root, rel.endsWith('/') ? rel + 'index.html' : rel);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404);res.end();return; }
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(fs.readFileSync(file));
  });
  await new Promise(done => server.listen(0,'127.0.0.1',done));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({headless:true}), report = [];
  try {
    for (const width of [320,390,1440]) {
      const context = await browser.newContext({viewport:{width,height:900},locale:'ja-JP'});
      await context.route('**/*', r => new URL(r.request().url()).origin === origin ? r.continue() : r.abort());
      const page = await context.newPage(), errors = [];
      page.on('pageerror', err=>errors.push(err.message));
      for(const mode of ['snapshot','fallback']) {
        const response = await page.goto(origin + route + (mode === 'fallback' ? 'fallback-qa.html' : '') + '?test=1',
          {waitUntil:'networkidle'});
        assert.equal(response.status(),200);
        assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'),
          'https://stusaurus.github.io/food-cost-jp/guides/rice-5kg-10kg-household-plan/');
        assert.equal(await page.locator('#required-kg').innerText(),'9kg');
        assert.equal(await page.locator('#to-buy-kg').innerText(),'9kg');
        assert.equal(await page.locator('#five-sets').innerText(),'5kgセット × 2');
        assert.equal(await page.locator('#ten-sets').innerText(),'10kgセット × 1');
        assert.equal(await page.locator('#five-leftover').innerText(),'見込み残量 1kg');
        const count = await page.locator('article[data-rice-offer]').count();
        if(mode === 'fallback') {
          assert.equal(count,0);
          assert.equal(await page.locator('a[data-affiliate="rakuten"]').count(),0);
          assert.equal(await page.locator('#five-total').innerText(),'価格比較は一時停止中');
          assert.equal(await page.locator('#ten-total').innerText(),'価格比較は一時停止中');
          assert.equal(await page.locator('#best-total').innerText(),'価格比較は一時停止中');
          assert.match(await page.locator('h1').innerText(),/購入セット数/);
        } else {
          assert([0,2].includes(count));
          if(count===2) {
            const price5 = Number(await page.locator('[data-rice-offer][data-kg="5"]').getAttribute('data-price'));
            const price10 = Number(await page.locator('[data-rice-offer][data-kg="10"]').getAttribute('data-price'));
            assert(Number.isInteger(price5) && price5>0 && Number.isInteger(price10) && price10>0);
            assert.equal(await page.locator('#five-total').innerText(),(2*price5).toLocaleString('ja-JP')+'円');
            assert.equal(await page.locator('#ten-total').innerText(),price10.toLocaleString('ja-JP')+'円');
            assert.equal(await page.locator('a[data-affiliate="rakuten"]').count(),2);
          } else {
            assert.equal(await page.locator('#five-total').innerText(),'価格比較は一時停止中');
            assert.equal(await page.locator('a[data-affiliate="rakuten"]').count(),0);
          }
        }
        await page.locator('#go-day').fill('3');
        assert.equal(await page.locator('#results').isVisible(),false);
        await page.locator('#calculate').click();
        assert.equal(await page.locator('#required-kg').innerText(),'13.5kg');
        assert.equal(await page.locator('#five-sets').innerText(),'5kgセット × 3');
        assert.equal(await page.locator('#ten-sets').innerText(),'10kgセット × 2');
        await page.locator('#stock').fill('20');
        await page.locator('#calculate').click();
        assert.equal(await page.locator('#to-buy-kg').innerText(),'0kg');
        assert.equal(await page.locator('#five-sets').innerText(),'5kgセット × 0');
        await page.locator('#go-day').fill('0');
        await page.locator('#calculate').click();
        assert.equal(await page.locator('#results').isVisible(),false);
        assert.match(await page.locator('#status').innerText(),/入力範囲内/);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+2);
        assert.equal(overflow,false,'horizontal overflow at '+width+'px in '+mode);
        assert.deepEqual(errors,[],'browser console errors at '+width+'px in '+mode);
        await page.locator('#go-day').fill('2');
        await page.locator('#stock').fill('0');
        await page.locator('#calculate').click();
        await page.screenshot({path:output+'/'+mode+'-'+width+'.png',fullPage:true});
        report.push({viewport:width,mode,offers:count,quantityAndStock:true,unknownPriceHidden:count===0,
          externalRequestsBlocked:true,overflow:false,errors});
      }
      await context.close();
    }
    fs.writeFileSync(output+'/report.json',JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});