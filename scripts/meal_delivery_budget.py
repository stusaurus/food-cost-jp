"""Budget planner for chilled family meal delivery, separate from Rakuten pricing.

The source-owned A8 creative and impression pixel are never rewritten.
Actual price and shipping are supplied by the reader; the published examples
are merely editable references from the provider's own public FAQ.
"""
from pathlib import Path
import html

SLUG = "family-meal-delivery-budget"
BASE = "https://stusaurus.github.io/food-cost-jp/"
URL = BASE + "guides/" + SLUG + "/"
MARKER = "<!-- chef-muten-family-budget-entry-v1 -->"

A8_CHEF_MUTEN = '''<a href="https://px.a8.net/svt/ejp?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM" rel="nofollow">お子様にも安心！"添加物不使用"のつくりおきおかず</a>
<img border="0" width="1" height="1" src="https://www19.a8.net/0.gif?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM" alt="">'''

# The provider's published examples are not prices guaranteed by this site.
# Keep them as opt-in inputs, not automatically filled "current prices".
EXAMPLES = {
    "support": {"first": 3799, "first_shipping": 0, "regular": 5173, "regular_shipping": 990, "dinners": 2},
    "omakase": {"first": 9980, "first_shipping": 0, "regular": 13607, "regular_shipping": 990, "dinners": 3},
}


def page(analytics_markup=""):
    markup = r'''<!doctype html><html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>冷蔵つくりおき宅配の料金はいくら？初回・送料・4週間の支払総額を計算｜食品コスパ比較</title>
<meta name="description" content="シェフの無添つくりおきなど冷蔵宅配おかずを検討する家庭向け。初回価格・通常価格・送料・配送回数を入力して4週間の実際の支払総額と家族の夕食1回あたりの目安を計算。">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://stusaurus.github.io/food-cost-jp/guides/family-meal-delivery-budget/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"食品コスパ比較","item":"https://stusaurus.github.io/food-cost-jp/"},{"@type":"ListItem","position":2,"name":"つくりおき宅配の料金計算","item":"https://stusaurus.github.io/food-cost-jp/guides/family-meal-delivery-budget/"}]}</script>
<style>
:root{--ink:#283b30;--muted:#52665b;--bg:#f7f4ed;--paper:#fffefa;--line:#dedfd4;--green:#286047}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",system-ui,sans-serif;color:var(--ink);background:var(--bg);line-height:1.75}
a{color:#226445;text-underline-offset:3px}
.wrap{max-width:940px;margin:0 auto;padding:16px clamp(16px,4vw,30px) 68px}
.masthead{border-bottom:1px solid var(--line);background:#fffdf8}
.masthead .wrap{display:flex;align-items:center;justify-content:space-between;gap:10px;padding-top:14px;padding-bottom:14px}
.masthead a{text-decoration:none;font-weight:800}
.tag{font-size:12px;color:var(--muted)}
.kicker{font-size:12px;font-weight:800;color:#4f7860;letter-spacing:.08em;margin:27px 0 5px}
h1{font-size:clamp(27px,5vw,39px);line-height:1.43;margin:8px 0 12px}
h2{font-size:clamp(19px,3vw,25px);line-height:1.45;margin:0 0 12px}
.lead{color:#475d4f;font-size:16px;line-height:1.9;max-width:780px}
.box{margin:22px 0;padding:clamp(18px,3.3vw,28px);border-radius:17px;background:var(--paper);border:1px solid var(--line)}
.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px 18px}
label{display:grid;gap:5px;font-size:14px;font-weight:750}
label small{font-size:12px;font-weight:450;color:var(--muted)}
input,select{width:100%;min-width:0;min-height:48px;border-radius:9px;border:1px solid #9eafa3;background:#fff;color:var(--ink);font:inherit;font-size:16px;padding:10px 12px}
input:focus-visible,select:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #91b69f;outline-offset:3px}
input[type=checkbox]{width:20px;min-height:20px;height:20px}
.checkline{display:flex;align-items:center;gap:11px;margin:18px 0 7px;font-size:14px;font-weight:650}
.checkline span{flex:1}
.btn{min-height:48px;padding:12px 19px;border:0;border-radius:10px;background:var(--green);color:white;font-size:16px;font-weight:800;cursor:pointer}
.btn.secondary{background:#e8efe8;color:#25533d;border:1px solid #acccaf}
.btn:hover{filter:brightness(.94)}
.actions{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 0}
.actions>*{flex:1;min-width:185px}
.muted{font-size:13px;line-height:1.85;color:var(--muted)}
.reference{border-left:4px solid #acc3ab;padding-left:13px;margin:14px 0}
[hidden]{display:none!important}
.results{border-top:1px solid var(--line);padding-top:22px;margin-top:22px}
.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.metric{background:#f1f7ee;border:1px solid #d3e4d0;padding:15px;border-radius:11px}
.metric span{font-size:12px;display:block}.metric strong{font-size:clamp(22px,3.5vw,30px);display:block}
.breakdown{margin:16px 0 5px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.breakdown dt{font-size:12px;color:var(--muted)}.breakdown dd{margin:3px 0 0;font-weight:800}
.notice{background:#f5f1e6;padding:14px 16px;border-radius:11px;font-size:13px;line-height:1.8}
ul{padding-left:22px}li{margin:11px 0}
.sponsor{background:#eff5ed;border:2px solid #b8d1bb}
.ad-label{font-size:12px;font-weight:800;color:#45604d}
.sponsor-creative{margin:18px 0 11px}
.sponsor-creative a{display:block;max-width:730px;min-height:48px;background:#285b44;border-radius:11px;color:#fff;text-decoration:none;padding:15px 17px;font-weight:800;font-size:16px;line-height:1.6;overflow-wrap:anywhere}
.sponsor-creative a:hover{background:#1d4433}
.home-link{display:inline-block;margin:9px 0 0}
@media(max-width:600px){.form-grid,.metrics,.breakdown{grid-template-columns:1fr}.actions{flex-direction:column}.actions>*{min-width:0;width:100%}.masthead .tag{display:none}}
</style>
__ANALYTICS__
</head>
<body>
<header class="masthead"><div class="wrap"><a href="https://stusaurus.github.io/food-cost-jp/">食品コスパ比較</a><span class="tag">家族の食費・購入判断</span></div></header>
<main class="wrap">
<p class="kicker">FAMILY MEAL COST PLANNER</p>
<h1>つくりおき宅配の4週間の料金はいくら？</h1>
<p class="lead">初回限定価格だけで決めず、2回目以降の商品代・送料・配送回数まで計算します。
週末にまとめて食べたい家庭にも、忙しい平日の夕食を一部置き換えたい家庭にも、実際の支払いを判断するための計算機です。</p>
<p class="muted">このページは「シェフの無添つくりおき」の公式公開情報を参考にしています。
冷蔵のおかず宅配であり、冷凍幼児食とは保存方法が異なります。
栄養上の適合や食品の安全性を当サイトが保証するものではありません。</p>

<section class="box" id="meal-budget" aria-labelledby="meal-form-title">
<h2 id="meal-form-title">4週間で実際に払う金額を計算</h2>
<p class="muted">以下は税込の入力欄です。プランの最新価格・初回割引・送料は、申込画面で確認して入力してください。
スキップする週がある場合は配送回数を減らしてください。</p>
<form id="meal-form" novalidate>
<div class="form-grid">
<label>検討するプラン
<select id="meal-plan">
<option value="support">食卓サポート（家族3人・夕食約2回分の想定）</option>
<option value="omakase">食卓おまかせ（家族4人・夕食約3回分の想定）</option>
</select>
<small>分量・実際の食事回数は家庭ごとに変わります。</small></label>
<label>4週間で受け取る回数（0〜4回）
<input id="meal-deliveries" type="number" min="0" max="4" step="1" inputmode="numeric" value="4" required>
<small>毎週なら4回。スキップを予定する場合は減らしてください。</small></label>
<label>初回の商品代金（税込・円）
<input id="meal-first-price" type="number" min="0" max="1000000" step="1" inputmode="numeric" placeholder="初回注文画面の値" required></label>
<label>初回の送料（税込・円）
<input id="meal-first-shipping" type="number" min="0" max="1000000" step="1" inputmode="numeric" placeholder="無料なら0" required></label>
<label>2回目以降の商品代金（税込・円）
<input id="meal-regular-price" type="number" min="0" max="1000000" step="1" inputmode="numeric" placeholder="通常商品代金" required></label>
<label>2回目以降の送料（税込・円）
<input id="meal-regular-shipping" type="number" min="0" max="1000000" step="1" inputmode="numeric" placeholder="1配送分の送料" required></label>
</div>
<label class="checkline"><input id="meal-include-first" type="checkbox" checked><span>4週間の受取回数に初回注文を含める（既存会員はチェックを外す）</span></label>
<div class="reference">
<p class="muted"><b>入力例（公式料金案内を2026年11月3日に参照）</b>：食卓サポートは初回3,799円・送料無料、2回目以降は5,173円＋送料990円。
食卓おまかせは初回9,980円・送料無料、2回目以降は13,607円＋送料990円。現在の価格・条件とは異なる場合があります。</p>
</div>
<div class="actions">
<button class="btn secondary" id="meal-example" type="button">選択プランの参考金額を入力</button>
<button class="btn" id="meal-calculate" type="submit">4週間の支払額を計算する</button>
</div>
<p id="meal-error" class="muted" role="status" aria-live="polite">未入力の項目がある場合、金額は表示しません。</p>
</form>
<div class="results" id="meal-results" hidden aria-live="polite">
<h2>あなたの入力条件での結果（4週間）</h2>
<div class="metrics">
<div class="metric"><span>4週間で払う商品代・送料の合計</span><strong id="meal-total"></strong></div>
<div class="metric"><span>家族の夕食1回あたりの目安</span><strong id="meal-per-dinner"></strong></div>
</div>
<dl class="breakdown">
<div><dt>期間内の配送回数</dt><dd id="meal-orders"></dd></div>
<div><dt>商品代金の合計</dt><dd id="meal-product-total"></dd></div>
<div><dt>送料の合計</dt><dd id="meal-shipping-total"></dd></div>
<div><dt>想定の家族の夕食回数（セット分量から換算）</dt><dd id="meal-dinners"></dd></div>
</dl>
<p id="meal-verdict" class="notice"></p>
<p class="muted">家族の夕食1回あたりは「公式の想定家族人数・日数」を基準に便宜的に割ったものです。
1人1食の価格ではありません。4週間の支払額は入力した配送回数・条件に基づく概算で、実際の決済や消費期限、スキップ可否を保証しません。</p>
</div>
</section>

<section class="box" aria-labelledby="meal-check-title">
<h2 id="meal-check-title">注文前の確認ポイント</h2>
<ul>
<li><strong>定期便・配送日：</strong>基本は毎週の定期配送。初回だけの購入を予定する場合も、次回便が確定する前に手続きが必要です。</li>
<li><strong>スキップ・休止期限：</strong>公式FAQでは次回お届けの6日前が原則、一部地域は7日前と案内されています。初回注文分のスキップはできない旨も記載されています。</li>
<li><strong>冷蔵の消費期限：</strong>公式案内ではお届け日を含め4日間（一部エリアは3日間）です。冷凍品と同じ長期保存は想定しないでください。</li>
<li><strong>お子様との食事：</strong>提供メニュー・原材料・アレルギー表示・年齢に合う分量を注文前に確認してください。広告文の「安心」は、個別の安全性やアレルギー対応を保証しません。</li>
</ul>
<p class="muted">情報源：<a href="https://store.tavenal.com/faq" rel="noopener">公式FAQ（料金・定期便）</a>、
<a href="https://store.tavenal.com/tsukurioki/" rel="noopener">公式サービス・価格案内</a>。
参照時点の公開情報であり、現在の契約条件は必ず販売ページで確認してください。</p>
</section>

<section class="box sponsor" id="chef-muten-ad" aria-labelledby="meal-ad-title">
<p class="ad-label">広告｜A8.netアフィリエイト</p>
<h2 id="meal-ad-title">シェフの無添つくりおきを検討する</h2>
<p>家族向けの冷蔵おかず宅配サービスです。プランごとの食事量・注文額・送料・配送地域と、次回配送の変更期限を確認してから、
上の計算機に金額を入力できます。</p>
<div class="sponsor-creative">__A8_OFFICIAL_CREATIVE__</div>
<p class="muted">リンク内の宣伝文句は広告主提供の表現です。当サイトでは「必ず安心」「誰にでも適合」などの保証はしません。
広告リンクから購入すると当サイトに成果報酬が発生する場合があります。広告の有無は計算結果に影響しません。</p>
</section>
<a class="home-link" href="https://stusaurus.github.io/food-cost-jp/">← 食品コスパ比較トップへ戻る</a>
</main>
<script>
(() => {
  const $ = id => document.getElementById(id);
  const form = $('meal-form');
  const examples = {
    support: {first:3799, first_shipping:0, regular:5173, regular_shipping:990, dinners:2},
    omakase: {first:9980, first_shipping:0, regular:13607, regular_shipping:990, dinners:3}
  };
  const fields = [['meal-first-price',0,1000000],['meal-first-shipping',0,1000000],
                  ['meal-regular-price',0,1000000],['meal-regular-shipping',0,1000000]];
  const money = n => Math.round(n).toLocaleString('ja-JP') + '円';
  $('meal-example').addEventListener('click', () => {
    const x = examples[$('meal-plan').value];
    if (!x) return;
    $('meal-first-price').value = x.first;
    $('meal-first-shipping').value = x.first_shipping;
    $('meal-regular-price').value = x.regular;
    $('meal-regular-shipping').value = x.regular_shipping;
    $('meal-results').hidden = true;
    $('meal-error').textContent = '2026年11月3日に参照した公式公開例を入力しました。最新の注文条件をご確認ください。';
  });
  form.addEventListener('submit', e => {
    e.preventDefault();
    $('meal-results').hidden = true;
    const plan = examples[$('meal-plan').value];
    const ordersRaw = $('meal-deliveries').value.trim();
    const orders = Number(ordersRaw);
    if (!plan || !ordersRaw || !Number.isInteger(orders) || orders < 0 || orders > 4) {
      $('meal-error').textContent = '配送回数は0〜4回の整数で入力してください。';
      return;
    }
    const values = {};
    for (const [id, min, max] of fields) {
      const raw = $(id).value.trim(), n = Number(raw);
      if (!raw || !Number.isSafeInteger(n) || n < min || n > max) {
        $('meal-error').textContent = '商品代金・送料は0以上の整数で、すべての欄を入力してください。';
        return;
      }
      values[id] = n;
    }
    const firstCount = orders > 0 && $('meal-include-first').checked ? 1 : 0;
    const regularCount = orders - firstCount;
    const products = firstCount * values['meal-first-price'] + regularCount * values['meal-regular-price'];
    const shipping = firstCount * values['meal-first-shipping'] + regularCount * values['meal-regular-shipping'];
    const total = products + shipping, dinners = orders * plan.dinners;
    $('meal-total').textContent = money(total);
    $('meal-per-dinner').textContent = dinners > 0 ? money(total / dinners) : '―';
    $('meal-orders').textContent = orders + '回（初回 ' + firstCount + '回・通常 ' + regularCount + '回）';
    $('meal-product-total').textContent = money(products);
    $('meal-shipping-total').textContent = money(shipping);
    $('meal-dinners').textContent = dinners + '回相当';
    $('meal-verdict').textContent = orders > 0
      ? '初回と通常料金、1配送ごとの送料を分けて計算しました。配送をスキップする週があれば実際の配送回数に合わせて見直してください。'
      : '4週間の配送を0回とした試算です。注文確定済みの便や変更期限によっては費用が発生する場合があります。';
    $('meal-error').textContent = '入力値に基づく試算です。最新価格・注文状況と照合してください。';
    $('meal-results').hidden = false;
    if (typeof window.gtag === 'function') window.gtag('event','meal_budget_calculate',{
      site_id:'food_cost_jp', meal_service:'chef_muten', category_id:'family_meal_delivery',
      operator_test:window.foodCostOperatorTest?'1':'0'
    });
  });
  const ad = document.querySelector('#chef-muten-ad a[href^="https://px.a8.net/svt/ejp?"]');
  if (ad) ad.addEventListener('click', () => {
    if (typeof window.gtag === 'function') window.gtag('event','affiliate_click',{
      site_id:'food_cost_jp', affiliate:'a8', program:'chef_muten_tsukurioki',
      category_id:'family_meal_delivery', conversion_source:'family_meal_budget_planner',
      click_position:'family_meal_sponsored_card', operator_test:window.foodCostOperatorTest?'1':'0'
    });
  });
})();
</script>
</body></html>'''
    if markup.count("__A8_OFFICIAL_CREATIVE__") != 1 or markup.count("__ANALYTICS__") != 1:
        raise ValueError("meal budget markup placeholders missing")
    output = markup.replace("__A8_OFFICIAL_CREATIVE__", A8_CHEF_MUTEN).replace("__ANALYTICS__", analytics_markup)
    validate_creative(output)
    return output


def validate_creative(markup: str) -> None:
    if markup.count(A8_CHEF_MUTEN) != 1:
        raise ValueError("A8 official creative must be preserved exactly once")
    if markup.count('href="https://px.a8.net/svt/ejp?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM" rel="nofollow"') != 1:
        raise ValueError("wrong A8 destination")
    if markup.count('src="https://www19.a8.net/0.gif?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM"') != 1:
        raise ValueError("wrong A8 pixel")
    if markup.count("広告｜A8.netアフィリエイト") != 1:
        raise ValueError("missing ad disclosure")


def inject_home(path: Path) -> None:
    markup = path.read_text(encoding="utf-8")
    if MARKER in markup:
        return
    if markup.count("</main>") != 1:
        raise ValueError("unexpected home HTML layout")
    entry = (
        MARKER
        + '<section class="section" id="family-meal-budget-entry" style="max-width:980px;margin:24px auto;padding:24px;background:#f2f7ee;border:1px solid #c4d7c8;border-radius:17px">'
        + '<p class="section-kicker">HOME MEAL BUDGET</p>'
        + '<h2>冷蔵つくりおき宅配、4週間の食費はいくら？</h2>'
        + '<p>初回の割引額だけでなく、2回目以降の料金・送料・スキップする週も入力して、実際に払う金額を計算できます。</p>'
        + f'<a href="{URL}" style="display:inline-block;padding:12px 18px;min-height:48px;border-radius:10px;background:#286047;color:white;font-weight:800;text-decoration:none">家族の食費を試算する →</a>'
        + '</section>'
    )
    path.write_text(markup.replace("</main>", entry + "\n</main>", 1), encoding="utf-8")


def publish(site: Path = Path("site"), analytics_markup: str = "") -> Path:
    if not (site / "index.html").exists() or not (site / "sitemap.xml").exists():
        raise ValueError("generated site must exist")
    target = site / "guides" / SLUG / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page(analytics_markup), encoding="utf-8")
    inject_home(site / "index.html")
    sitemap = site / "sitemap.xml"
    xml = sitemap.read_text(encoding="utf-8")
    if xml.count("</urlset>") != 1:
        raise ValueError("unexpected sitemap format")
    loc = "<url><loc>" + html.escape(URL, quote=False) + "</loc></url>"
    if URL not in xml:
        sitemap.write_text(xml.replace("</urlset>", loc + "</urlset>", 1), encoding="utf-8")
    return target
