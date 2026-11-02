"""Generate one source-owned, independent drinking-water cost comparison.

No fabricated service price, merchant claims, or unapproved ASP tracking links.
All calculations stay in the browser. Existing Rakuten product links are unchanged.
"""
from pathlib import Path
import html

SLUG = "water-server-vs-bottled-water"
BASE = "https://stusaurus.github.io/food-cost-jp/"
URL = BASE + "guides/" + SLUG + "/"
MARKER = '<!-- water-cost-decision-pilot-v1 -->'


def page():
    return r'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ウォーターサーバーとペットボトルはどっちが安い？年間費用を比較｜食品コスパ比較</title>
<meta name="description" content="ペットボトル水のケース価格・送料と、ウォーターサーバーの月額・水代・電気代・初期費用を入力。家族の水使用量から1年間の実支出と余剰水を比較できる無料計算機です。">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://stusaurus.github.io/food-cost-jp/guides/water-server-vs-bottled-water/">
<style>
:root{--bg:#f7f3e9;--paper:#fffdf8;--green:#285242;--ink:#263b31;--line:#dedbca;--muted:#58675d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.75}
a{color:var(--green)}.wrap{max-width:850px;margin:auto;padding:18px 20px 70px}
.brand{display:flex;gap:14px;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:12px 0}
.brand a{text-decoration:none;font-weight:800}.tag{font-size:12px;color:var(--muted)}
h1{font-size:clamp(27px,5vw,38px);line-height:1.45;margin:21px 0}
h2{font-size:clamp(19px,3vw,25px);line-height:1.4;margin:0 0 10px}
.lead{font-size:15px;line-height:1.95;color:var(--muted)}
.box{background:var(--paper);border:1px solid var(--line);border-radius:17px;padding:clamp(17px,3vw,28px);margin:20px 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:grid;gap:5px;font-weight:700;font-size:13px}
input{width:100%;padding:12px;min-height:44px;border:1px solid #b9c6b8;border-radius:9px;background:#fff;font-size:16px}
input:focus-visible,a:focus-visible{outline:3px solid #88a992;outline-offset:3px}
small,.muted{color:var(--muted);font-size:12px}
.notice{padding:12px;border-radius:9px;background:#f2eee1;font-size:13px}
button{border:0;border-radius:12px;background:var(--green);color:white;font-size:16px;font-weight:800;padding:13px 25px;min-height:48px;cursor:pointer}
.results{display:none}.results.visible{display:block}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.metric{padding:15px;border:1px solid var(--line);border-radius:12px;background:white}
.metric strong{font-size:clamp(19px,3.5vw,28px);display:block}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px 8px;text-align:left;border-bottom:1px solid var(--line)}td:last-child{text-align:right;font-weight:700}
.cta{display:block;margin:12px 0;background:var(--green);border-radius:11px;text-align:center;color:white;padding:13px 18px;text-decoration:none;font-weight:800}
ul{padding-left:24px}li{margin:9px 0}
@media(max-width:640px){.cols,.metrics{grid-template-columns:1fr}.brand .tag{display:none}.wrap{padding:15px 14px 50px}}
</style>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","name":"ウォーターサーバーとペットボトルの年間費用比較","url":"https://stusaurus.github.io/food-cost-jp/guides/water-server-vs-bottled-water/","description":"入力値だけで両方式の費用を計算する無料比較ツール"}</script>
</head>
<body>
<div class="wrap">
<div class="brand"><a href="../../">食品コスパ比較</a><span class="tag">飲みもの・暮らしのコストを整理する</span></div>
<main>
<p class="tag">家庭の水代を比べるツール</p>
<h1>ウォーターサーバーとペットボトル、どっちが安い？</h1>
<p class="lead">世帯人数だけで「お得」は決まりません。毎月飲む量、買う水の容量・送料、ウォーターサーバーの固定費や水代まで入れて、<strong>1年間に実際に払う費用</strong>を比べます。金額は各社の最新条件を確認して入力してください。</p>
<section class="box" aria-labelledby="bottle-title">
<h2 id="bottle-title">1. ペットボトルの買い方</h2>
<div class="cols">
<label>1か月に使う水の量（L）<input id="liters" type="number" inputmode="decimal" min="0.1" max="10000" step="0.1" placeholder="例：48" required></label>
<label>1本の容量（L）<input id="bottle-liters" type="number" inputmode="decimal" min="0.1" max="100" step="0.1" placeholder="例：2" required></label>
<label>1ケースの本数<input id="case-count" type="number" inputmode="numeric" min="1" max="1000" step="1" placeholder="例：6" required></label>
<label>1ケースの商品価格（税込・円）<input id="case-price" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：900" required></label>
<label>1ケースの送料（円）<input id="case-shipping" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：0（送料無料）" required></label>
</div>
<p class="muted">ケース単位で必要本数を切り上げます。年間の購入分は余剰を翌月に使う想定です。水の品質や冷却・保管・運搬の手間は金額に含みません。</p>
</section>
<section class="box" aria-labelledby="server-title">
<h2 id="server-title">2. ウォーターサーバーの契約条件</h2>
<div class="cols">
<label>月額固定費・レンタル料（円）<input id="monthly-fee" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：3000" required></label>
<label>水代・従量料金（1Lあたり円）<input id="server-per-liter" type="number" inputmode="decimal" min="0" max="100000" step="0.01" placeholder="例：0（定額制の場合）" required></label>
<label>電気代など月間追加費用（円）<input id="electric" type="number" inputmode="numeric" min="0" max="1000000" step="1" placeholder="例：500" required></label>
<label>設置・契約時の一時費用（円）<input id="upfront" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：0" required></label>
</div>
<p class="muted">解約違約金・最低注文量・配送料・メンテナンス料などは、該当する場合に入力費用へ含めてください。水道直結型や浄水型は水源・水道料金・フィルター条件が異なるため、契約条件を確認してください。</p>
</section>
<section class="box">
<button id="calculate" type="button">年間支払額を比較する</button>
<p id="error" class="notice" role="status" aria-live="polite">数値を入力すると比較できます。入力内容は外部に送信しません。</p>
<div id="results" class="results" aria-live="polite">
<h2>12か月の比較結果</h2>
<div class="metrics">
<div class="metric"><small>ペットボトルの年間購入額</small><strong id="bottle-year"></strong></div>
<div class="metric"><small>サーバーの年間支払額</small><strong id="server-year"></strong></div>
</div>
<p id="verdict" class="notice"></p>
<div class="table-wrap"><table><tbody>
<tr><th scope="row">1年に買うペットボトル</th><td id="bottle-count"></td></tr>
<tr><th scope="row">ペットボトル購入量</th><td id="purchased-liters"></td></tr>
<tr><th scope="row">年間の使用予定量</th><td id="used-liters"></td></tr>
<tr><th scope="row">ペットボトルの余剰</th><td id="leftover-liters"></td></tr>
<tr><th scope="row">サーバー年間固定・追加費用</th><td id="server-fixed"></td></tr>
</tbody></table></div>
<p class="muted">飲み水だけを比べています。温水の利便性、電源・設置面積、水の種類や味は比較に含めていません。</p>
</div>
</section>
<section class="box">
<h2>比較する前に見るべきポイント</h2>
<ul>
<li><strong>使い切れる量：</strong>ケース買いは1年分の使用量に対して端数のボトルが残ります。</li>
<li><strong>毎月の最低購入数：</strong>配送型サーバーはノルマやスキップ条件によって支払額が変わります。</li>
<li><strong>解約・設置費用：</strong>最初の1年間は初期費用、長期利用時は交換費用や契約期間も確認してください。</li>
<li><strong>安全性と用途：</strong>乳幼児の調乳用途などはコストだけで判断せず、製品・自治体・医療機関の指示を確認してください。</li>
</ul>
<a class="cta" href="../../categories/mineral-water/">楽天のペットボトル水を送料込みで比較する</a>
<p class="muted">※上のリンク先には楽天アフィリエイト広告が含まれます。ウォーターサーバーの広告案件は提携確認前のため掲載していません。</p>
</section>
</main>
</div>
<script>
(() => {
"use strict";
const $ = id => document.getElementById(id);
const fields = ["liters","bottle-liters","case-count","case-price","case-shipping","monthly-fee","server-per-liter","electric","upfront"];
const money = amount => Math.round(amount).toLocaleString("ja-JP") + "円";
const litersText = amount => (Math.round(amount * 100) / 100).toLocaleString("ja-JP") + "L";
const error = $("error"), results = $("results");
$("calculate").addEventListener("click", () => {
  results.classList.remove("visible");
  const inputs = Object.fromEntries(fields.map(id => [id, Number($(id).value)]));
  if (fields.some(id => $(id).value.trim() === "" || !Number.isFinite(inputs[id]) ||
       inputs[id] < 0 || inputs[id] > Number($(id).max))) {
    error.textContent = "すべての項目に0以上の数値を入力してください。"; return;
  }
  const L = inputs.liters, b = inputs["bottle-liters"], c = inputs["case-count"];
  if (!(L > 0 && b > 0 && Number.isInteger(c) && c >= 1)) {
    error.textContent = "水の量・1本の容量は0より大きい数、ケース本数は整数で入力してください。"; return;
  }
  const cases = Math.ceil(L * 12 / (b * c));
  const bottles = cases * c, purchased = bottles * b, used = L * 12;
  const bottledYear = cases * (inputs["case-price"] + inputs["case-shipping"]);
  const fixedYear = (inputs["monthly-fee"] + inputs.electric) * 12 + inputs.upfront;
  const serverYear = fixedYear + used * inputs["server-per-liter"];
  if (![bottledYear,serverYear,purchased,used].every(Number.isFinite) ||
       Math.max(bottledYear,serverYear) > 10000000000) {
    error.textContent = "入力値が大きすぎます。条件を確認してください。"; return;
  }
  $("bottle-year").textContent = money(bottledYear);
  $("server-year").textContent = money(serverYear);
  $("bottle-count").textContent = bottles + "本（" + cases + "ケース）";
  $("purchased-liters").textContent = litersText(purchased);
  $("used-liters").textContent = litersText(used);
  $("leftover-liters").textContent = litersText(Math.max(0,purchased-used));
  $("server-fixed").textContent = money(fixedYear);
  const gap = Math.abs(bottledYear-serverYear);
  $("verdict").textContent = bottledYear < serverYear ? "入力した条件ではペットボトルが年間" + money(gap) + "安い計算です。"
    : bottledYear > serverYear ? "入力した条件ではサーバーが年間" + money(gap) + "安い計算です。"
    : "入力した条件では年間支払額は同額です。";
  error.textContent = "入力条件をもとに計算しました。";
  results.classList.add("visible");
});
})();
</script>
</body>
</html>'''


def inject_link(page):
    if not page.exists():
        raise ValueError("missing publication target " + str(page))
    content = page.read_text(encoding="utf-8")
    if MARKER in content:
        return
    if content.count("</main>") != 1:
        raise ValueError("unexpected page layout " + str(page))
    snippet = (
        MARKER + '<aside class="water-cost-entry" style="margin:26px auto;'
        'padding:20px;border:1px solid #dedbca;border-radius:14px;'
        'background:#fffdf8;max-width:900px">'
        '<h2 style="font-size:22px">水のまとめ買いとウォーターサーバー、年間ではどちらが安い？</h2>'
        '<p>価格だけでなく送料・電気代・必要本数まで比べられる無料計算機です。</p>'
        '<a href="/food-cost-jp/guides/water-server-vs-bottled-water/">年間支払額を計算する →</a>'
        '</aside>'
    )
    page.write_text(content.replace("</main>", snippet + "</main>", 1), encoding="utf-8")


def publish(site=Path("site")):
    if not (site / "index.html").exists() or not (site / "sitemap.xml").exists():
        raise ValueError("generated site must exist")
    target = site / "guides" / SLUG / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page(), encoding="utf-8")
    inject_link(site / "index.html")
    inject_link(site / "categories" / "mineral-water" / "index.html")
    sitemap = site / "sitemap.xml"
    content = sitemap.read_text(encoding="utf-8")
    loc = "<url><loc>" + html.escape(URL, quote=False) + "</loc></url>"
    if content.count("</urlset>") != 1:
        raise ValueError("invalid sitemap")
    if URL not in content:
        sitemap.write_text(content.replace("</urlset>", loc + "</urlset>", 1), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(publish())
