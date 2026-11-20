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

# Preserve the A8.net ad creative exactly, including its attribution pixel.
A8_EVERY_FRECIOUS_AD = '''<a href="https://px.a8.net/svt/ejp?a8mat=4BGCF1+53DLEY+2B8Y+15OK2A" rel="nofollow">【every frecious（エブリィフレシャス）】</a>
<img border="0" width="1" height="1" src="https://www17.a8.net/0.gif?a8mat=4BGCF1+53DLEY+2B8Y+15OK2A" alt="">'''



def verified_water_offer_markup(offers=None, checked_at=None):
    """Use only validated, postage-included current water offers from the catalog."""
    sizes = {}
    for offer in offers or []:
        q = offer.get("quantity") or {}
        count, volume, total = q.get("count"), q.get("unit_volume_ml"), q.get("total_volume_ml")
        price, confidence, url = offer.get("price"), q.get("confidence", 0), offer.get("url") or ""
        if offer.get("postage_included") is not True or offer.get("shipping_status") != "included":
            continue
        if not isinstance(url, str) or not url.startswith("https://hb.afl.rakuten.co.jp/"):
            continue
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               for v in (count, volume, total, price, confidence)):
            continue
        if not float(count).is_integer() or not float(price).is_integer():
            continue
        if not (1 <= count <= 1000 and 100 <= volume <= 100000
                and 1 <= price <= 10000000 and confidence >= 0.9
                and abs(count * volume - total) < 0.001):
            continue
        if volume not in sizes or price / total < sizes[volume]["price"] / sizes[volume]["total"]:
            sizes[volume] = dict(offer=offer, count=int(count), volume=volume,
                                 total=total, price=int(price))
    choices = sorted(sizes.values(), key=lambda x: (x["price"] / x["total"], x["price"]))[:3]
    if not choices:
        return ""
    checked = f"{checked_at:%Y-%m-%d %H:%M} JST" if checked_at is not None else "掲載データ取得時点"
    cards = []
    for choice in choices:
        offer = choice["offer"]
        name = html.escape(str(offer.get("name") or "ミネラルウォーター")[:100])
        count, price, volume_l = choice["count"], choice["price"], choice["volume"] / 1000
        per_liter = price * 1000 / choice["total"]
        url = html.escape(offer["url"], quote=True)
        product_id = html.escape(str(offer.get("id") or ""), quote=True)
        cards.append(
            '<article class="water-offer-card">'
            f'<p class="water-offer-name">{name}</p>'
            f'<p><strong>{volume_l:g}L×{count}本 · ¥{price:,}／購入セット</strong>'
            f'<small>掲載内 ¥{per_liter:,.1f}／L · 送料込み判定</small></p>'
            f'<button type="button" data-water-offer data-bottle-liters="{volume_l:g}"'
            f' data-case-count="{count}" data-case-price="{price}">この掲載商品を入力する</button>'
            f'<a href="{url}" target="_blank" rel="nofollow sponsored noopener"'
            f' data-water-rakuten-offer data-product-id="{product_id}">楽天で条件を確認</a>'
            '</article>'
        )
    return (
        '<section class="box" aria-labelledby="verified-water-title">'
        '<h2 id="verified-water-title">掲載商品の価格から試算する</h2>'
        f'<p class="muted">最終価格確認：{html.escape(checked)}。'
        '送料込み判定済みの掲載商品の中から、容量別に単価が低いものを表示しています。'
        '楽天全体の最安値ではありません。</p>'
        '<div class="water-offer-grid">' + "".join(cards) + '</div>'
        '<p class="muted">選ぶと購入セットの容量・本数・商品価格・送料0円を入力します。'
        '配送地域別の追加送料・現在の在庫・最終支払額は販売店で確認してください。'
        '月の使用量・サーバー料金はご自身の条件で入力してください。</p>'
        '</section>'
    )


def page(analytics_markup="", water_offers=None, checked_at=None):
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
.calculate-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
#example{background:white;color:var(--green);border:1px solid var(--green)}
.metric .cost-detail{display:block;line-height:1.7;margin-top:4px}
#example-warning{margin-top:12px}
.results{display:none}.results.visible{display:block}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.metric{padding:15px;border:1px solid var(--line);border-radius:12px;background:white}
.metric strong{font-size:clamp(19px,3.5vw,28px);display:block}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px 8px;text-align:left;border-bottom:1px solid var(--line)}td:last-child{text-align:right;font-weight:700}
.cta{display:block;margin:12px 0;background:var(--green);border-radius:11px;text-align:center;color:white;padding:13px 18px;text-decoration:none;font-weight:800}
.sponsor-box{border:2px solid #cad8cf;background:#f0f5ed}
.sponsor-box .ad-label{display:inline-block;margin:0 0 9px;font-size:12px;font-weight:700;color:#48574d}
.sponsor-box .sponsor-link a{display:block;padding:15px 17px;min-height:48px;border-radius:11px;background:#285242;color:white;text-decoration:none;text-align:center;font-size:16px;font-weight:700}
.sponsor-box .sponsor-link a:focus-visible{outline:3px solid #88a992;outline-offset:3px}
.sponsor-box .sponsor-link{margin:15px 0 10px}
ul{padding-left:24px}li{margin:9px 0}
.water-offer-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.water-offer-card{min-width:0;border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff}
.water-offer-name{font-size:13px;font-weight:700;line-height:1.6;overflow-wrap:anywhere}
.water-offer-card strong{display:block;font-size:15px}.water-offer-card small{display:block}
.water-offer-card button{font-size:14px;padding:10px;width:100%;margin-top:7px}
.water-offer-card a{display:block;margin-top:9px;font-size:13px;text-align:center}
#bottle-source-note{margin-top:12px}
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
__VERIFIED_WATER_OFFERS__
<section class="box" aria-labelledby="bottle-title">
<h2 id="bottle-title">1. ペットボトルの買い方</h2>
<div class="cols">
<label>1か月に使う水の量（L）<input id="liters" type="number" inputmode="decimal" min="0.1" max="10000" step="0.1" placeholder="例：48" required></label>
<label>1本の容量（L）<input id="bottle-liters" type="number" inputmode="decimal" min="0.1" max="100" step="0.1" placeholder="例：2" required></label>
<label>1購入セットの本数<input id="case-count" type="number" inputmode="numeric" min="1" max="1000" step="1" placeholder="例：6" required></label>
<label>1購入セットの商品価格（税込・円）<input id="case-price" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：900" required></label>
<label>1購入セットの送料（円）<input id="case-shipping" type="number" inputmode="numeric" min="0" max="10000000" step="1" placeholder="例：0（送料無料）" required></label>
</div>
<p id="bottle-source-note" class="notice" hidden>掲載商品から条件を入力しました。価格・配送地域別の送料は販売店で再確認してください。</p>
<p class="muted">購入セット単位で必要本数を切り上げます。年間の購入分は余剰を翌月に使う想定です。水の品質や冷却・保管・運搬の手間は金額に含みません。</p>
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
<div class="calculate-actions">
<button id="calculate" type="button">年間支払額を比較する</button>
<button id="example" type="button">仮の入力例で試す</button>
</div>
<p id="example-warning" class="notice" hidden>※これは計算方法を確かめるための仮の数値です。現在の販売価格・各社の契約料金ではありません。ご自身の購入先・契約先の最新条件に入力し直して判断してください。</p>
<p id="error" class="notice" role="status" aria-live="polite">数値を入力すると比較できます。入力内容は外部に送信しません。</p>
<div id="results" class="results" aria-live="polite">
<h2>12か月の比較結果</h2>
<div class="metrics">
<div class="metric"><small>ペットボトルの年間購入額</small><strong id="bottle-year"></strong><small id="bottle-monthly" class="cost-detail"></small><small id="bottle-effective" class="cost-detail"></small></div>
<div class="metric"><small>サーバーの年間支払額</small><strong id="server-year"></strong><small id="server-monthly" class="cost-detail"></small><small id="server-effective" class="cost-detail"></small></div>
</div>
<p id="verdict" class="notice"></p>
<div class="table-wrap"><table><tbody>
<tr><th scope="row">1年に買うペットボトル</th><td id="bottle-count"></td></tr>
<tr><th scope="row">ペットボトル購入量</th><td id="purchased-liters"></td></tr>
<tr><th scope="row">年間の使用予定量</th><td id="used-liters"></td></tr>
<tr><th scope="row">ペットボトルの余剰</th><td id="leftover-liters"></td></tr>
<tr><th scope="row">サーバー年間固定・追加費用</th><td id="server-fixed"></td></tr>
</tbody></table></div>
<p class="muted">月平均は年間支払額を12で割った参考値です。購入セットは必要数を年間で切り上げるため、実際の月ごとの支払額は均等ではありません。1Lあたりの額は年間購入量ではなく年間使用予定量を基準に算出します。温水の利便性、電源・設置面積、水の種類や味は比較に含めていません。</p>
</div>
</section>
<section class="box sponsor-box" id="a8-every-frecious-ad" aria-label="広告・ウォーターサーバー">
<p class="ad-label">広告｜A8.netアフィリエイト</p>
<h2>ウォーターサーバーの契約条件を確認する</h2>
<p>浄水型ウォーターサーバーの選択肢として、エブリィフレシャスの案内ページを確認できます。月額料金・電気代・初期費用・契約期間・解約条件を確認し、上の計算機に入力してください。</p>
<p class="sponsor-link">__A8_EVERY_FRECIOUS_CREATIVE__</p>
<p class="muted">広告を経由して契約すると、サイトに報酬が発生する場合があります。広告の有無は年間費用の計算結果や判定に影響しません。</p>
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
<p class="muted">※上のリンク先には楽天アフィリエイト広告が含まれます。ウォーターサーバーの広告は別途「広告」と表示しています。</p>
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
// Outbound ad clicks use the site's established GA4 event and operator filter.
const a8Creative = document.querySelector("#a8-every-frecious-ad a[href^='https://px.a8.net/svt/ejp?']");
if (a8Creative) a8Creative.addEventListener("click", () => {
  if (typeof window.gtag === "function") window.gtag("event", "affiliate_click", {
    site_id: "food_cost_jp",
    affiliate: "a8",
    program: "every_frecious",
    category_id: "mineral-water",
    conversion_source: "water_server_cost_comparison",
    click_position: "water_comparison_sponsored_link",
    operator_test: window.foodCostOperatorTest ? "1" : "0"
  });
});
// Never leave an old annual quote visible after a household or price input changes.
fields.forEach(id => {
  const invalidate = () => {
    if (!results.classList.contains("visible")) return;
    results.classList.remove("visible");
    error.textContent = "条件が変わりました。新しい金額を見るには、もう一度「年間支払額を比較する」を押してください。";
  };
  const clearSource = () => {
    if (["bottle-liters", "case-count", "case-price", "case-shipping"].includes(id))
      $("bottle-source-note").hidden = true;
  };
  $(id).addEventListener("input", () => { invalidate(); clearSource(); });
  $(id).addEventListener("change", () => { invalidate(); clearSource(); });
});
// Example inputs are deliberately hypothetical. Never present them as vendor prices.
$("example").addEventListener("click", () => {
  const sample = {
    "liters": 48, "bottle-liters": 2, "case-count": 6,
    "case-price": 900, "case-shipping": 0, "monthly-fee": 3000,
    "server-per-liter": 0, "electric": 500, "upfront": 0
  };
  Object.entries(sample).forEach(([id, value]) => { $(id).value = String(value); });
  $("example-warning").hidden = false;
  $("bottle-source-note").hidden = true;
  $("calculate").click();
});
// Source prices are from this site's validated catalog; do not trust query-string prices.
document.querySelectorAll("[data-water-offer]").forEach(button => {
  button.addEventListener("click", () => {
    [["bottle-liters", "bottleLiters"], ["case-count", "caseCount"],
     ["case-price", "casePrice"]].forEach(([id, attr]) => {
      $(id).value = button.dataset[attr];
    });
    $("case-shipping").value = "0";
    results.classList.remove("visible");
    $("bottle-source-note").hidden = false;
    error.textContent = "掲載商品の購入セット条件を入力しました。使用量・サーバー契約料金を入力して試算してください。";
    if (typeof window.gtag === "function") window.gtag("event", "water_offer_prefill", {
      site_id: "food_cost_jp", category_id: "mineral-water",
      operator_test: window.foodCostOperatorTest ? "1" : "0"
    });
  });
});
document.querySelectorAll("a[data-water-rakuten-offer]").forEach(link => {
  link.addEventListener("click", () => {
    if (typeof window.gtag === "function") window.gtag("event", "affiliate_click", {
      site_id: "food_cost_jp", affiliate: "rakuten", category_id: "mineral-water",
      conversion_source: "water_server_cost_comparison",
      click_position: "water_cost_verified_offer",
      operator_test: window.foodCostOperatorTest ? "1" : "0"
    });
  });
});
$("calculate").addEventListener("click", () => {
  results.classList.remove("visible");
  const inputs = Object.fromEntries(fields.map(id => [id, Number($(id).value)]));
  if (fields.some(id => $(id).value.trim() === "" || !Number.isFinite(inputs[id]) ||
       inputs[id] < 0 || inputs[id] > Number($(id).max))) {
    error.textContent = "すべての項目に0以上の数値を入力してください。"; return;
  }
  if (fields.some(id => !$(id).checkValidity())) {
    error.textContent = "入力範囲と入力単位を確認してください。金額・ケース本数は整数で入力してください。"; return;
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
  $("bottle-monthly").textContent = "月平均 " + money(bottledYear / 12);
  $("server-monthly").textContent = "月平均 " + money(serverYear / 12);
  const usedLiterPrice = amount => (amount / used).toLocaleString("ja-JP", {
    minimumFractionDigits: 1, maximumFractionDigits: 1
  }) + "円／L";
  $("bottle-effective").textContent = "使用予定1Lあたり " + usedLiterPrice(bottledYear);
  $("server-effective").textContent = "使用予定1Lあたり " + usedLiterPrice(serverYear);
  $("bottle-count").textContent = bottles + "本（" + cases + "購入セット）";
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
</html>'''.replace("__A8_EVERY_FRECIOUS_CREATIVE__", A8_EVERY_FRECIOUS_AD, 1).replace("__VERIFIED_WATER_OFFERS__", verified_water_offer_markup(water_offers, checked_at), 1).replace("</head>", analytics_markup + "\n</head>", 1)


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


def publish(site=Path("site"), analytics_markup="", water_offers=None, checked_at=None):
    if not (site / "index.html").exists() or not (site / "sitemap.xml").exists():
        raise ValueError("generated site must exist")
    target = site / "guides" / SLUG / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page(analytics_markup, water_offers, checked_at), encoding="utf-8")
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
