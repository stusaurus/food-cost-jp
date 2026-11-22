"""A persistent household rice purchasing calculator, even when seller offers are missing.

Rice weights are UNCOOKED. 1 go ~= 150g is sourced from MAFF; no cooked
rice conversion, invented energy price, coupon, or merchant minimum is assumed.
Only the existing vetted, shipping-included offer feed can supply prices.
"""
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
import html
import json
import math
from zoneinfo import ZoneInfo

SLUG = "rice-5kg-10kg-household-plan"
BASE = "https://stusaurus.github.io/food-cost-jp/"
URL = BASE + "guides/" + SLUG + "/"
MARKER = "<!-- household-rice-amount-planner-v1 -->"
MAFF = "https://www.maff.go.jp/j/heya/kodomo_sodan/0103/01.html"
JST = ZoneInfo("Asia/Tokyo")
MAX_OFFER_AGE = timedelta(hours=48)


def price_is_fresh(checked_at: datetime | None, now: datetime | None = None) -> bool:
    """Never show prices from a snapshot older than 48 hours or without its source time.

    Legacy snapshot timestamps without a zone are recorded in Japan local time.
    """
    if checked_at is None:
        return False
    checked = checked_at if checked_at.tzinfo else checked_at.replace(tzinfo=JST)
    current = now or datetime.now(JST)
    current = current if current.tzinfo else current.replace(tzinfo=JST)
    age = current.astimezone(timezone.utc) - checked.astimezone(timezone.utc)
    return timedelta(0) <= age <= MAX_OFFER_AGE


def eligible_offers(items):
    """Choose one verified seller offer each for exact TOTAL 5kg and 10kg sets."""
    chosen = {}
    for item in items or []:
        q = item.get("quantity") or {}
        grams = q.get("total_weight_g")
        price = item.get("price")
        confidence = q.get("confidence")
        product_id, url = item.get("id"), item.get("url")
        if item.get("postage_included") is not True or item.get("shipping_status") != "included":
            continue
        if any(isinstance(x, bool) or not isinstance(x, (float, int))
               for x in (grams, price, confidence)):
            continue
        if grams not in (5000, 10000) or not float(price).is_integer():
            continue
        if not (1 <= price <= 10000000 and confidence >= 0.9):
            continue
        if not isinstance(product_id, str) or not product_id:
            continue
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "hb.afl.rakuten.co.jp" or not parsed.path.startswith("/hgc/"):
            continue
        destination = urlparse(parse_qs(parsed.query).get("pc", [""])[0])
        if destination.scheme != "https" or destination.hostname != "item.rakuten.co.jp":
            continue
        title = str(item.get("name") or "")
        if "配送不可" in title or "送料別" in title or "一部地域除く" in title:
            continue
        if grams not in chosen or (price, product_id) < (chosen[grams]["price"], chosen[grams]["id"]):
            chosen[grams] = item
    return chosen if set(chosen) == {5000, 10000} else {}


def offer_card(item, grams):
    price = int(item["price"])
    size = grams // 1000
    title = html.escape(str(item.get("name") or "米")[:110])
    url = html.escape(item["url"], quote=True)
    product_id = html.escape(item["id"], quote=True)
    per_kg = price * 1000 / grams
    return (
        f'<article class="offer" data-rice-offer data-kg="{size}" data-price="{price}">'
        f'<span class="eyebrow">{size}kgセットの掲載候補</span>'
        f'<h3>{title}</h3>'
        f'<div class="price">¥{price:,}<small>送料込み判定／{size}kgセット</small></div>'
        f'<p class="small">掲載内で ¥{per_kg:,.1f}／kg。'
        '10kgセットが5kg×2袋で届く場合もあります。</p>'
        f'<a class="buy" href="{url}" target="_blank" rel="nofollow sponsored noopener"'
        f' data-affiliate="rakuten" data-position="rice_household_planner"'
        f' data-category="rice" data-product-id="{product_id}" data-metric="per_kg"'
        f' data-unit-price="{per_kg:.6f}" data-shipping="included">楽天で購入条件を確認する</a>'
        '</article>'
    )


def page(items, checked_at: datetime | None = None, analytics_markup="", now: datetime | None = None):
    offers = eligible_offers(items)
    has_offers = bool(offers) and price_is_fresh(checked_at, now)
    checked = checked_at.strftime("%Y-%m-%d %H:%M JST") if checked_at else "掲載データ取得時点"
    checked = html.escape(checked)
    checked_iso = (checked_at.replace(tzinfo=JST) if checked_at and checked_at.tzinfo is None else checked_at)
    checked_iso = html.escape(checked_iso.isoformat(), quote=True) if checked_iso else ""
    cards = (offer_card(offers[5000], 5000) + offer_card(offers[10000], 10000)) if has_offers else ""
    document = r'''<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>米5kg・10kgは何日もつ？家族の必要量と購入総額を計算｜食品コスパ比較</title>
<meta name="description" content="1日何合、何日分、手持ちのお米の在庫から必要な精米kgを算出。米5kg・10kg・組み合わせ購入で何セット必要か、送料込み掲載価格で実際の購入総額と余りを比較します。">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://stusaurus.github.io/food-cost-jp/guides/rice-5kg-10kg-household-plan/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","name":"米5kg・10kgは何日もつ？家庭の必要量・購入総額計算","url":"https://stusaurus.github.io/food-cost-jp/guides/rice-5kg-10kg-household-plan/","inLanguage":"ja-JP","description":"検証済み精米5kg・10kg商品の送料込み掲載価格と家庭の消費量・在庫を使った購入計画計算機"}</script>
<style>
:root{--ink:#263d31;--green:#285644;--bg:#f7f3e9;--paper:#fffefa;--line:#d7dfd4;--muted:#56665c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:980px;margin:auto;padding:20px 16px 70px}a{color:var(--green)}.top{display:flex;justify-content:space-between;align-items:center;gap:14px;border-bottom:1px solid var(--line);padding:12px 0}
.top a{font-weight:800;text-decoration:none}.tag,.eyebrow{font-size:12px;color:var(--muted)}h1{font-size:clamp(28px,4.5vw,42px);line-height:1.45;margin:24px 0 14px}
h2{font-size:clamp(20px,3vw,26px);line-height:1.4;margin:0 0 12px}h3{font-size:17px;line-height:1.6;margin:8px 0}
.lead{font-size:16px;color:var(--muted);max-width:790px}.box{background:var(--paper);border:1px solid var(--line);padding:clamp(16px,3vw,26px);border-radius:16px;margin:20px 0}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.inputs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
label{display:grid;gap:5px;font-weight:700;font-size:14px}input{min-width:0;width:100%;border:1px solid #a0b5a5;border-radius:10px;padding:12px;font-size:17px;background:white;color:var(--ink);min-height:48px}
button{border:0;border-radius:11px;background:var(--green);color:white;font-size:16px;font-weight:700;padding:12px 24px;min-height:48px;cursor:pointer}
:where(button,a,input):focus-visible{outline:3px solid #83a88b;outline-offset:3px}
.offer,.result-card{border:1px solid var(--line);border-radius:12px;background:#fff;padding:16px;min-width:0}
.price{font-weight:800;font-size:23px}.price small{display:block;font-size:12px;font-weight:500;color:var(--muted)}
.buy{display:block;background:var(--green);border-radius:10px;color:#fff;text-align:center;font-size:14px;font-weight:700;text-decoration:none;padding:12px;margin-top:10px;min-height:48px}
.small,.note{font-size:13px;color:var(--muted)}.note{background:#f0eee5;padding:14px;border-radius:10px}
.result-card strong{font-size:clamp(21px,3vw,29px);display:block}.result-card small{display:block;color:var(--muted);font-size:13px}
.result-card.best{border:2px solid var(--green)}.summary strong{font-size:19px}.summary{display:flex;gap:20px;flex-wrap:wrap}
[hidden]{display:none!important}
@media(max-width:700px){.inputs,.grid{grid-template-columns:1fr}.top .tag{display:none}main{padding:16px 14px 56px}}
</style>
</head><body><main>
<div class="top"><a href="../../">食品コスパ比較</a><span class="tag">購入する量と価格の根拠を確かめる</span></div>
<p class="tag">家族の米の買い方・計算ツール</p>
<h1>米5kg・10kgは何日もつ？必要量と購入総額を計算</h1>
<p class="lead">1日何合のお米を炊くか、何日分を買うか、今あるお米は何kgかを入れると、<strong>5kgだけ・10kgだけ・組み合わせ</strong>の購入セット数、支払総額、購入後の余りを比較できます。</p>
<section class="box" aria-labelledby="basis-title">
<h2 id="basis-title">米5kgは約33.3合、10kgは約66.7合</h2>
<p>計算には<strong>精米1合＝約150g（炊く前のお米）</strong>を使います。例えば1日2合なら、5kgは約16.7日分、10kgは約33.3日分。炊飯後のご飯の重量とは異なります。炊飯器の水加減・蒸発・食べ残しなどは別の要因です。</p>
<p class="small">換算根拠：<a href="https://www.maff.go.jp/j/heya/kodomo_sodan/0103/01.html" target="_blank" rel="noopener">農林水産省「お米の重さとご飯の重さの違い」</a>。日数は毎日同じ合数を使う場合の計算値です。</p>
</section>
<section class="box" aria-labelledby="seller-title" id="seller-section" data-checked-at="__CHECKED_ISO__">
<h2 id="seller-title">__SELLER_TITLE__</h2>
<p class="note">__SELLER_NOTE__</p>
__SELLER_CARDS__
</section>
<section class="box" aria-labelledby="form-title">
<h2 id="form-title">家族で必要なお米を計算</h2>
<div class="inputs">
<label for="go-day">1日あたり炊く米（合）<input id="go-day" type="number" inputmode="decimal" min="0.1" max="20" step="0.1" value="2" required></label>
<label for="days">買い置きしたい日数（日）<input id="days" type="number" inputmode="numeric" min="1" max="365" step="1" value="30" required></label>
<label for="stock">手元にある精米（kg）<input id="stock" type="number" inputmode="decimal" min="0" max="200" step="0.1" value="0" required></label>
</div>
<p class="small">目安として「1日2合 × 30日」なら9kg。世帯人数ではなく、実際に炊く合数で計算します。在庫は炊く前の精米重量で入力してください。</p>
<button id="calculate" type="button">必要な購入量を計算</button>
<p id="status" class="note" role="status" aria-live="polite">初期値でも計算できます。値を変えたときは計算ボタンを押してください。</p>
<div id="results" hidden aria-live="polite">
<div class="summary">
<p>必要な精米：<strong id="required-kg"></strong></p>
<p>在庫差引の購入必要量：<strong id="to-buy-kg"></strong></p>
</div>
<div class="grid">
<article class="result-card"><h3>5kgセットだけで買う</h3><strong id="five-total"></strong><span id="five-sets"></span><small id="five-leftover"></small></article>
<article class="result-card"><h3>10kgセットだけで買う</h3><strong id="ten-total"></strong><span id="ten-sets"></span><small id="ten-leftover"></small></article>
</div>
<article class="result-card best" style="margin-top:14px"><h3>__BEST_TITLE__</h3><strong id="best-total"></strong><div id="best-sets"></div><small id="best-leftover"></small></article>
<p class="note">__RESULT_NOTE__</p>
</div>
</section>
<section class="box"><h2>5kgと10kg、何を基準に選ぶ？</h2>
<p>1kg単価が安くても、必要量が少なければ買い過ぎになる場合があります。逆に10kgセットは5kg袋2つで届く場合があるため、<strong>袋の数ではなく商品の販売セット総量</strong>で比較しています。</p>
<p>30日分を買うなら、まず「1日の炊飯合数 × 30日」を計算し、手元の在庫を引いてください。2合/日なら必要な精米は9kg。5kgを2セット買う場合と10kgを1セット買う場合では、余りが同じでも支払額が異なることがあります。</p>
<p><a href="../../categories/rice/">送料込み米の全商品ランキングを見る</a>　／　<a href="../../categories/pack-rice/">パックご飯を1食単価で比較する</a></p>
<p class="small">当サイトは楽天アフィリエイトを利用しています。広告を経由した購入で報酬が発生する場合があります。結果は掲載データと入力条件に基づく計算であり、購入や商品の推奨を保証するものではありません。</p>
</section>
</main>
<script>
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const a5 = document.querySelector('[data-rice-offer][data-kg="5"]');
  const a10 = document.querySelector('[data-rice-offer][data-kg="10"]');
  const seller = el("seller-section");
  const sellerNote = seller.querySelector(".note");
  const offerGrid = seller.querySelector(".grid");
  const priceMaxAgeMs = 48 * 60 * 60 * 1000;
  const checkedAtMs = Date.parse(seller.dataset.checkedAt || "");
  let hasPrices = !!(a5 && a10);
  function enforcePriceExpiry() {
    if (!hasPrices) return;
    const age = Date.now() - checkedAtMs;
    if (Number.isFinite(checkedAtMs) && age >= 0 && age <= priceMaxAgeMs) return;
    hasPrices = false;
    if (offerGrid) offerGrid.hidden = true;
    el("seller-title").textContent = "掲載商品の価格比較は現在確認中です";
    sellerNote.textContent = "掲載商品データが48時間を超えた、または取得日時を確認できないため、価格・購入リンクを非表示にしています。必要量と購入セット数は引き続き計算できます。";
    document.querySelectorAll('a[data-affiliate="rakuten"]').forEach(link => {
      link.removeAttribute("href");
      link.hidden = true;
    });
    el("best-total").textContent = "価格比較は一時停止中";
    el("five-total").textContent = "価格比較は一時停止中";
    el("ten-total").textContent = "価格比較は一時停止中";
    calculate(false);
  }
  const price5 = hasPrices ? Number(a5.dataset.price) : null;
  const price10 = hasPrices ? Number(a10.dataset.price) : null;
  const yen = v => Math.round(v).toLocaleString("ja-JP") + "円";
  const kg = v => (Math.round(v * 100) / 100).toLocaleString("ja-JP", {maximumFractionDigits:2}) + "kg";
  const countFor = (neededGrams, packGrams) => Math.max(0, Math.ceil(neededGrams / packGrams - 1e-10));
  const inputs = ["go-day", "days", "stock"];
  function invalidate() {
    el("results").hidden = true;
    el("status").textContent = "入力が変わりました。新しい購入数量は再計算してください。";
  }
  inputs.forEach(id => {
    el(id).addEventListener("input", invalidate);
    el(id).addEventListener("change", invalidate);
  });
  function calculate(userAction) {
    const go = Number(el("go-day").value);
    const days = Number(el("days").value);
    const stock = Number(el("stock").value);
    if (inputs.some(id => !el(id).value.trim() || !el(id).checkValidity()) ||
        ![go,days,stock].every(Number.isFinite) ||
        go < 0.1 || go > 20 || !Number.isInteger(days) || days < 1 || days > 365 ||
        stock < 0 || stock > 200) {
      el("results").hidden = true;
      el("status").textContent = "合数・日数・在庫を入力範囲内で指定してください。";
      return;
    }
    const requiredG = go * 150 * days;
    const buyG = Math.max(0, requiredG - stock * 1000);
    const five = countFor(buyG, 5000);
    const ten = countFor(buyG, 10000);
    const spentFive = hasPrices ? five * price5 : null;
    const spentTen = hasPrices ? ten * price10 : null;
    const surplus = (purchasedG) => kg(Math.max(0, stock * 1000 + purchasedG - requiredG) / 1000);
    let best = null;
    if (hasPrices) {
      for (let t = 0; t <= ten; t++) {
        const f = countFor(Math.max(0, buyG - 10000 * t), 5000);
        const cost = f * price5 + t * price10;
        const boughtG = f * 5000 + t * 10000;
        if (!best || cost < best.cost ||
            (cost === best.cost && (boughtG < best.boughtG ||
            (boughtG === best.boughtG && f + t < best.f + best.t)))) {
          best = {f:f,t:t,cost:cost,boughtG:boughtG};
        }
      }
    }
    el("required-kg").textContent = kg(requiredG / 1000);
    el("to-buy-kg").textContent = kg(buyG / 1000);
    el("five-total").textContent = hasPrices ? yen(spentFive) : "価格比較は一時停止中";
    el("five-sets").textContent = "5kgセット × " + five;
    el("five-leftover").textContent = "見込み残量 " + surplus(five * 5000);
    el("ten-total").textContent = hasPrices ? yen(spentTen) : "価格比較は一時停止中";
    el("ten-sets").textContent = "10kgセット × " + ten;
    el("ten-leftover").textContent = "見込み残量 " + surplus(ten * 10000);
    el("best-total").textContent = hasPrices ? yen(best.cost) : "価格比較は一時停止中";
    el("best-sets").textContent = hasPrices ?
      "5kgセット × " + best.f + "、10kgセット × " + best.t :
      "検証済みの5kg・10kg商品が両方そろっていないため、最安組み合わせは計算できません。";
    el("best-leftover").textContent = hasPrices ? "見込み残量 " + surplus(best.boughtG) : "";
    el("status").textContent = hasPrices ? "表示した商品の掲載価格と入力条件で算出しました。" :
      "必要量と各サイズのセット数を計算しました。掲載価格の比較は確認中です。";
    el("results").hidden = false;
    if (userAction && typeof window.gtag === "function") window.gtag("event", "rice_household_plan", {
      site_id:"food_cost_jp", operator_test:window.foodCostOperatorTest ? "1" : "0"
    });
  }
  el("calculate").addEventListener("click", () => {
    enforcePriceExpiry();
    calculate(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) enforcePriceExpiry();
  });
  window.addEventListener("focus", enforcePriceExpiry);
  document.querySelectorAll('a[data-affiliate="rakuten"]').forEach(link => {
    link.addEventListener("click", event => {
      enforcePriceExpiry();
      if (!hasPrices) {
        event.preventDefault();
        return;
      }
      if (typeof window.gtag === "function") window.gtag("event", "affiliate_click", {
        site_id:"food_cost_jp",affiliate:"rakuten",category_id:"rice",
        conversion_source:"rice_household_planner",click_position:"rice_household_planner",
        operator_test:window.foodCostOperatorTest ? "1" : "0"
      });
    });
  });
  enforcePriceExpiry();
  calculate(false);
})();
</script></body></html>'''
    if has_offers:
        seller_title = "実際の掲載価格で比べる"
        seller_note = (f"掲載価格の最終確認：{checked}。各重量で、当サイトの送料込み判定済み商品の中から"
                       "商品セット価格が低い候補を使用。楽天市場全体の最安値・品質順位ではありません。"
                       "送料込み判定でも配送地域・在庫・発送日・最終決済額は購入先で再確認してください。"
                       "クーポンやポイント還元は差し引きません。")
        seller_cards = '<div class="grid">' + cards + '</div>'
        best_title = "この2商品で支払総額が低い組み合わせ"
        result_note = ("ここでの「最安」は表示した5kg商品・10kg商品の掲載価格だけを比較した結果です。"
                       "セット単位で購入するため余りが出ます。炊飯費用、送料の地域差、食べ残し、"
                       "保管中の品質変化は含めません。保管場所や消費期限も考えて購入してください。")
    else:
        seller_title = "掲載商品の価格比較は現在確認中です"
        seller_note = ("現時点で、送料込み判定・正確な販売セット重量・楽天の購入リンクを確認できた"
                       "5kgと10kgの両方の商品がそろっていません。未確認価格・未確認購入リンクは表示しません。"
                       "価格比較は停止していますが、家庭の必要量・5kgまたは10kgの必要セット数と余りは計算できます。")
        seller_cards = ""
        best_title = "5kgと10kgの組み合わせ価格は確認中"
        result_note = ("5kgと10kgの購入セット数は精米の必要量から計算しています。"
                       "両サイズの検証済み掲載価格がそろうまで支払総額や最安組み合わせは表示しません。"
                       "保管場所と消費予定も踏まえて購入を判断してください。")
        if offers and not price_is_fresh(checked_at, now):
            seller_note = (f"掲載商品データの最終取得：{checked}。48時間以内に確認できた価格ではないため、"
                           "購入価格・購入リンクは表示していません。必要量とセット数は計算できます。")
        # Do not advertise an unavailable seller-price calculation in search snippets.
        document = (document
            .replace("家族の必要量と購入総額を計算｜食品コスパ比較",
                     "家族の必要量と購入セット数を計算｜食品コスパ比較")
            .replace("送料込み掲載価格で実際の購入総額と余りを比較します。",
                     "購入セット数と余りを計算します。掲載価格が両サイズで確認できたときだけ支払総額も比較します。")
            .replace("米5kg・10kgは何日もつ？必要量と購入総額を計算</h1>",
                     "米5kg・10kgは何日もつ？必要量と購入セット数を計算</h1>")
            .replace("5kgだけ・10kgだけ・組み合わせ", "5kgだけ・10kgだけ")
            .replace("購入セット数、支払総額、購入後の余りを比較できます。",
                     "購入セット数と余りを計算できます。価格比較は検証済みの商品がそろう場合のみ表示します。")
            .replace("検証済み精米5kg・10kg商品の送料込み掲載価格と家庭の消費量・在庫を使った購入計画計算機",
                     "家庭の精米消費量と在庫から必要量と購入セット数を計算するツール")
            .replace("家庭の必要量・購入総額計算",
                     "家庭の必要量・購入セット数計算"))
    return (document.replace("__CHECKED_ISO__", checked_iso, 1)
            .replace("__SELLER_TITLE__", seller_title, 1)
            .replace("__SELLER_NOTE__", seller_note, 1)
            .replace("__SELLER_CARDS__", seller_cards, 1)
            .replace("__BEST_TITLE__", best_title, 1)
            .replace("__RESULT_NOTE__", result_note, 1)
            .replace("</head>", analytics_markup + "\n</head>", 1))


def inject_link(path):
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if MARKER in content:
        return
    if content.count("</main>") != 1:
        raise ValueError("unexpected rice guide navigation: " + str(path))
    snippet = (
        MARKER + '<aside class="rice-household-entry" style="padding:22px;'
        'margin:25px 0;border:1px solid #d7dfd4;border-radius:14px;'
        'background:#fffefa"><h2>米5kg・10kg、うちでは何日もつ？</h2>'
        '<p>1日の合数・手持ち在庫から必要セット数と余りを計算。'
        '検証済みの商品価格がそろう場合のみ支払総額も比較できます。</p>'
        '<a href="/food-cost-jp/guides/rice-5kg-10kg-household-plan/">必要量と購入セット数を計算する →</a>'
        '</aside>'
    )
    path.write_text(content.replace("</main>", snippet + "</main>", 1), encoding="utf-8")


def publish(root=Path("site"), rice_offers=None, checked_at=None, analytics_markup=""):
    target = root / "guides" / SLUG / "index.html"
    document = page(rice_offers, checked_at, analytics_markup)
    if not (root / "index.html").exists() or not (root / "categories/rice/index.html").exists() or not (root / "sitemap.xml").exists():
        raise ValueError("rice guide requires generated home, rice category and sitemap")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    for relative in ("index.html", "categories/rice/index.html",
                     "guides/rice-5kg-cost/index.html", "guides/rice-10kg-cost/index.html"):
        inject_link(root / relative)
    sitemap = root / "sitemap.xml"
    xml = sitemap.read_text(encoding="utf-8")
    if xml.count("</urlset>") != 1:
        raise ValueError("invalid sitemap")
    link = "<url><loc>" + html.escape(URL) + "</loc></url>"
    if URL not in xml:
        sitemap.write_text(xml.replace("</urlset>", link + "</urlset>", 1), encoding="utf-8")
    return True
