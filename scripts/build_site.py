from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SITE_ID = "food_cost_jp"
SITE_URL = "https://stusaurus.github.io/food-cost-jp/"
API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
OUT = Path("site")
APP_ID = os.getenv("RAKUTEN_APPLICATION_ID", "").strip()
ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()
GA_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()

CATEGORIES = [
    {"id":"pack-rice","name":"パックご飯","emoji":"🍚","queries":["パックご飯 200g","パックご飯 180g"],"primary":"per_serving","primary_label":"1食あたり","secondary":"per_100g","secondary_label":"100gあたり","intro":"食数と内容量をそろえ、24食・40食などの箱違いを公平に比較します。"},
    {"id":"rice","name":"米","emoji":"🌾","queries":["米 5kg 送料無料","米 10kg 送料無料"],"primary":"per_kg","primary_label":"1kgあたり","secondary":None,"secondary_label":None,"intro":"5kg・10kgなど総重量が違う商品を1kgあたりへ換算します。"},
    {"id":"carbonated-water","name":"炭酸水","emoji":"🫧","queries":["炭酸水 500ml 24本","炭酸水 500ml 48本","炭酸水 1L"],"primary":"per_liter","primary_label":"1Lあたり","secondary":"per_bottle","secondary_label":"1本あたり","intro":"500ml・1L・24本・48本などを1Lあたりと1本あたりへ換算します。"},
    {"id":"oatmeal","name":"オートミール","emoji":"🥣","queries":["オートミール 1kg","オートミール 2kg"],"primary":"per_100g","primary_label":"100gあたり","secondary":"per_kg","secondary_label":"1kgあたり","intro":"1kg袋・複数袋セットを100gあたりと1kgあたりへ換算します。"},
]

LIMITED_RE = re.compile(r"(?:定期購入(?:のみ)?|定期便(?:のみ)?|初回限定|会員限定|新規限定)")
PROMO_RE = re.compile(r"(?:クーポン|セール|SALE|タイムセール|ポイント\s*\d+倍|お買い物マラソン)", re.I)
SELECTABLE_RE = re.compile(r"(?:選べる|容量を選択|サイズを選択|個数を選択|\d+\s*(?:kg|g|ml|L)\s*[~/〜]\s*\d+)", re.I)


def norm(text: str) -> str:
    return (
        unicodedata.normalize("NFKC", str(text or ""))
        .replace("×", "x")
        .replace("✕", "x")
        .replace("＊", "x")
        .replace("*", "x")
        .replace(",", "")
    )


def parse_quantity(title: str, category_id: str):
    text = norm(title)
    if SELECTABLE_RE.search(text):
        return None

    if category_id == "pack-rice":
        matches = list(re.finditer(
            r"(\d+(?:\.\d+)?)\s*g\s*x\s*(\d+)\s*(?:食|個|パック)",
            text,
            re.I,
        ))
        signatures = {(float(m.group(1)), int(m.group(2))) for m in matches}
        if len(signatures) != 1:
            return None
        grams, count = next(iter(signatures))
        if grams <= 0 or count <= 0:
            return None
        return {
            "total_weight_g": grams * count,
            "unit_weight_g": grams,
            "count": count,
            "confidence": 0.995,
            "evidence": matches[0].group(0),
        }

    if category_id in {"rice", "oatmeal"}:
        packages = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(kg|g)\s*x\s*(\d+)\s*(?:袋|個|パック|セット)?",
            text,
            re.I,
        ))
        if packages:
            signatures = {(m.group(1), m.group(2).lower(), m.group(3)) for m in packages}
            if len(signatures) != 1:
                return None
            m = packages[0]
            amount = float(m.group(1)) * (1000 if m.group(2).lower() == "kg" else 1)
            count = int(m.group(3))
            if amount <= 0 or count <= 0:
                return None
            return {
                "total_weight_g": amount * count,
                "unit_weight_g": amount,
                "count": count,
                "confidence": 0.99,
                "evidence": m.group(0),
            }

        singles = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(kg|g)(?!\s*x)",
            text,
            re.I,
        ))
        amounts = {
            float(m.group(1)) * (1000 if m.group(2).lower() == "kg" else 1)
            for m in singles
        }
        if len(amounts) != 1:
            return None
        amount = next(iter(amounts))
        return {
            "total_weight_g": amount,
            "unit_weight_g": amount,
            "count": 1,
            "confidence": 0.90,
            "evidence": singles[0].group(0),
        }

    if category_id == "carbonated-water":
        matches = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(ml|l)\s*x\s*(\d+)\s*(?:本|個|缶|パック|ケース|箱)?",
            text,
            re.I,
        ))
        signatures = {(m.group(1), m.group(2).lower(), m.group(3)) for m in matches}
        if len(signatures) != 1:
            return None
        m = matches[0]
        amount = float(m.group(1)) * (1000 if m.group(2).lower() == "l" else 1)
        count = int(m.group(3))
        if amount <= 0 or count <= 0:
            return None
        return {
            "total_volume_ml": amount * count,
            "unit_volume_ml": amount,
            "count": count,
            "confidence": 0.99,
            "evidence": m.group(0),
        }

    return None


def unit_prices(price: int, quantity: dict, category_id: str) -> dict:
    out = {}
    if category_id == "pack-rice":
        out["per_serving"] = price / quantity["count"]
        out["per_100g"] = price / (quantity["total_weight_g"] / 100)
    elif category_id == "rice":
        out["per_kg"] = price / (quantity["total_weight_g"] / 1000)
    elif category_id == "carbonated-water":
        out["per_liter"] = price / (quantity["total_volume_ml"] / 1000)
        out["per_bottle"] = price / quantity["count"]
    elif category_id == "oatmeal":
        out["per_100g"] = price / (quantity["total_weight_g"] / 100)
        out["per_kg"] = price / (quantity["total_weight_g"] / 1000)
    return out


def first_image(item: dict) -> str:
    values = item.get("mediumImageUrls") or item.get("smallImageUrls") or []
    if not values:
        return ""
    first = values[0] if isinstance(values, list) else values
    if isinstance(first, dict):
        first = first.get("imageUrl") or first.get("url")
    return str(first or "").replace("http://", "https://")


def fetch(query: str) -> list[dict]:
    params = {
        "applicationId": APP_ID,
        "keyword": query,
        "hits": 30,
        "format": "json",
        "formatVersion": 2,
        "availability": 1,
        "field": 0,
    }
    if AFFILIATE_ID:
        params["affiliateId"] = AFFILIATE_ID

    request = urllib.request.Request(
        API_URL + "?" + urllib.parse.urlencode(params),
        headers={
            "accessKey": ACCESS_KEY,
            "Origin": "https://stusaurus.github.io",
            "Referer": SITE_URL,
            "User-Agent": "food-cost-jp/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("items") or payload.get("Items") or []


def normalize_item(raw: dict, category: dict):
    item = raw.get("Item", raw) if isinstance(raw, dict) else {}
    name = str(item.get("itemName") or "").strip()
    try:
        price = int(float(item.get("itemPrice") or 0))
    except (TypeError, ValueError):
        return None

    if not name or price <= 0 or LIMITED_RE.search(norm(name)):
        return None

    quantity = parse_quantity(name, category["id"])
    if not quantity or quantity.get("confidence", 0) < 0.90:
        return None

    prices = unit_prices(price, quantity, category["id"])
    if category["primary"] not in prices:
        return None

    postage_included = str(item.get("postageFlag")) == "0"
    url = str(item.get("affiliateUrl") or item.get("itemUrl") or "")
    if not url:
        return None

    return {
        "id": str(item.get("itemCode") or url)[:180],
        "name": name,
        "price": price,
        "shop": str(item.get("shopName") or ""),
        "url": url,
        "image": first_image(item),
        "postage_included": postage_included,
        "shipping_status": "included" if postage_included else "extra_or_unknown",
        "quantity": quantity,
        "unit_prices": prices,
        "promotion_mentioned": bool(PROMO_RE.search(norm(name))),
    }


def collect(category: dict):
    rows = []
    for index, query in enumerate(category["queries"]):
        if index:
            time.sleep(1.1)
        try:
            rows.extend(fetch(query))
        except Exception as exc:
            print(f"fetch failed {category['id']} {query}: {exc}", file=sys.stderr)

    normalized = [x for x in (normalize_item(row, category) for row in rows) if x]

    seen = set()
    unique = []
    for item in normalized:
        key = (item["id"], item["price"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    key = lambda item: (
        item["unit_prices"][category["primary"]],
        item["price"],
    )
    included = sorted([x for x in unique if x["postage_included"]], key=key)[:30]
    other = sorted([x for x in unique if not x["postage_included"]], key=key)[:20]
    return included, other


def yen(value):
    if value is None:
        return "-"
    return f"¥{value:,.1f}" if value < 100 else f"¥{value:,.0f}"


def quantity_text(item: dict, category_id: str) -> str:
    q = item["quantity"]
    if category_id == "carbonated-water":
        return f"{q['unit_volume_ml']:g}ml×{q['count']}本 / 合計{q['total_volume_ml']/1000:g}L"

    grams = q.get("total_weight_g", 0)
    text = f"合計{grams/1000:g}kg" if grams >= 1000 else f"合計{grams:g}g"
    if q.get("count", 1) > 1:
        text += f" / {q['count']}個・食"
    return text


def ga_head() -> str:
    if not GA_ID:
        return ""
    safe = html.escape(GA_ID, quote=True)
    return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={safe}"></script>
<script>
window.dataLayer=window.dataLayer||[];
function gtag(){{dataLayer.push(arguments)}}
gtag('js',new Date());
gtag('config','{safe}',{{site_id:'{SITE_ID}'}});
</script>"""


CSS = """*{box-sizing:border-box}
body{margin:0;background:#f7f8f5;color:#1e2521;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.65}
a{color:inherit}.wrap{width:min(1060px,calc(100% - 28px));margin:auto}
header{background:#fff;border-bottom:1px solid #dfe5df;padding:28px 0 20px}
.brand{font-size:12px;font-weight:900;color:#25724a;text-decoration:none}
h1{font-size:clamp(28px,7vw,44px);line-height:1.2;margin:8px 0}
.lead,.sub,.note{color:#667069}
.nav{position:sticky;top:0;background:#fffffff0;border-bottom:1px solid #dfe5df;z-index:10}
.nav .wrap{display:flex;gap:8px;overflow:auto;padding:9px 14px}
.nav a{white-space:nowrap;text-decoration:none;border:1px solid #dfe5df;border-radius:999px;padding:7px 11px;background:#fff;font-size:12px;font-weight:700}
.grid{display:grid;gap:10px;margin:20px 0}
.card,.explain{background:#fff;border:1px solid #dfe5df;border-radius:16px;padding:16px;text-decoration:none}
.section{margin:28px 0 42px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.toolbar select{min-height:40px;border:1px solid #dfe5df;border-radius:10px;background:#fff;padding:0 10px}
.table{overflow:auto;background:#fff;border:1px solid #dfe5df;border-radius:15px}
table{border-collapse:collapse;width:100%;min-width:760px}
th,td{padding:10px;border-bottom:1px solid #e6ebe6;text-align:left;font-size:12px;vertical-align:top}
th{background:#f2f6f3}.unit{font-size:18px;font-weight:900;color:#25724a}
.tag{display:inline-block;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:800}
.ok{background:#eef7f1;color:#25724a}.warn{background:#fff4dc;color:#8a5a13}
.cta{display:inline-flex;justify-content:center;align-items:center;min-height:38px;padding:0 10px;border-radius:9px;background:#25724a;color:#fff;text-decoration:none;font-weight:800;white-space:nowrap}
footer{background:#fff;border-top:1px solid #dfe5df;padding:28px 0 40px;color:#667069;font-size:11px}
@media(min-width:720px){.grid{grid-template-columns:1fr 1fr}}"""


JS = """(()=>{
const K='food_cost_operator_test_v1',p=new URLSearchParams(location.search);
let op=false;
try{op=localStorage.getItem(K)==='1'}catch(e){}
if(p.get('test')==='1'||p.get('test')==='0'){
  op=p.get('test')==='1';
  try{op?localStorage.setItem(K,'1'):localStorage.removeItem(K)}catch(e){}
  const u=new URL(location.href);u.searchParams.delete('test');history.replaceState(history.state,'',u.href)
}
const send=(n,x={})=>{if(typeof gtag==='function')gtag('event',n,{site_id:'food_cost_jp',...(op?{operator_test:'1'}:{}),...x})};
document.addEventListener('click',e=>{
  const a=e.target.closest('a[data-affiliate]');if(!a)return;
  const x={affiliate:'rakuten',conversion_source:'category',category_id:a.dataset.category,product_id:a.dataset.productId,product_name:a.dataset.productName,rank:a.dataset.rank,comparison_metric:a.dataset.metric,unit_price:Number(a.dataset.unitPrice||0),shipping_status:a.dataset.shipping,click_position:'comparison_table',link_url:a.href};
  send('product_result_click',x);send('affiliate_click',x)
});
document.querySelectorAll('[data-sort]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]'),body=root.querySelector('tbody'),rows=[...body.querySelectorAll('tr')],m=s.value;
  rows.sort((a,b)=>Number(a.dataset[m]||Infinity)-Number(b.dataset[m]||Infinity));
  rows.forEach((r,i)=>{r.querySelector('[data-rank]').textContent=i+1;body.appendChild(r)});
  send('comparison_sort',{category_id:s.dataset.category,comparison_metric:m})
}));
document.querySelectorAll('[data-filter]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]');
  root.querySelectorAll('tbody tr').forEach(r=>r.hidden=s.value!=='all'&&r.dataset.bucket!==s.value);
  send('comparison_filter_use',{category_id:s.dataset.category,filter_value:s.value})
}))
})();"""


def bucket(item: dict, category_id: str) -> str:
    q = item["quantity"]
    if category_id == "pack-rice":
        return "small" if q["count"] <= 24 else "large"
    if category_id == "rice":
        return "small" if q["total_weight_g"] <= 5000 else "large"
    if category_id == "carbonated-water":
        return "small" if q["unit_volume_ml"] <= 600 else "large"
    if category_id == "oatmeal":
        return "small" if q["total_weight_g"] <= 1000 else "large"
    return "all"


def rows_html(items: list[dict], category: dict) -> str:
    rows = []
    for rank, item in enumerate(items, start=1):
        primary_metric = category["primary"]
        secondary_metric = category["secondary"]
        primary = item["unit_prices"][primary_metric]
        secondary = (
            f'<div>{html.escape(category["secondary_label"])} {yen(item["unit_prices"].get(secondary_metric))}</div>'
            if secondary_metric else ""
        )
        image = (
            f'<img src="{html.escape(item["image"], quote=True)}" alt="" width="64" height="64" loading="lazy" style="object-fit:contain">'
            if item["image"] else ""
        )
        shipping = '<span class="tag ok">送料込み</span>' if item["postage_included"] else '<span class="tag warn">送料別・要確認</span>'
        promo = '<span class="tag warn">セール/クーポン表記</span>' if item["promotion_mentioned"] else ""
        attrs = f'data-price="{item["price"]}" ' + " ".join(
            f'data-{key}="{value:.6f}"'
            for key, value in item["unit_prices"].items()
        )
        rows.append(
            f"""<tr data-bucket="{bucket(item, category['id'])}" {attrs}>
<td data-rank>{rank}</td>
<td>{image}</td>
<td><strong>{html.escape(item['name'])}</strong><div>{html.escape(item['shop'])}</div>{shipping} {promo}</td>
<td>{html.escape(quantity_text(item, category['id']))}</td>
<td>¥{item['price']:,}</td>
<td class="unit">{yen(primary)}<div style="font-size:11px;color:#667069">{html.escape(category['primary_label'])}</div>{secondary}</td>
<td><a class="cta" href="{html.escape(item['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{primary_metric}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}">楽天で価格を見る</a></td>
</tr>"""
        )
    return "".join(rows)


def comparison_table(items: list[dict], category: dict, title: str, note: str) -> str:
    if not items:
        return f'<section class="section"><h2>{html.escape(title)}</h2><p class="sub">比較できる商品を取得できませんでした。</p></section>'

    options = [
        f'<option value="{category["primary"]}">{category["primary_label"]}が安い順</option>',
        '<option value="price">商品価格が安い順</option>',
    ]
    if category["secondary"]:
        options.insert(
            1,
            f'<option value="{category["secondary"]}">{category["secondary_label"]}が安い順</option>',
        )

    return f"""<section class="section" data-comparison>
<h2>{html.escape(title)}</h2>
<p class="sub">{html.escape(note)}</p>
<div class="toolbar">
<select data-sort data-category="{category['id']}">{''.join(options)}</select>
<select data-filter data-category="{category['id']}">
<option value="all">容量・数量すべて</option>
<option value="small">少量側</option>
<option value="large">大容量側</option>
</select>
</div>
<div class="table"><table>
<thead><tr><th>順</th><th></th><th>商品</th><th>数量</th><th>商品価格</th><th>単価</th><th>販売先</th></tr></thead>
<tbody>{rows_html(items, category)}</tbody>
</table></div>
</section>"""


def page_head(title: str, description: str, canonical: str) -> str:
    return f"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description, quote=True)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<style>{CSS}</style>
{ga_head()}
</head><body>"""


def category_page(category: dict, included: list[dict], other: list[dict], updated: datetime) -> str:
    parts = [
        page_head(
            f"{category['name']}のコスパ比較｜{category['primary_label']}・送料込み",
            f"{category['name']}を{category['primary_label']}へ換算し、容量・セット数・送料条件をそろえて比較します。",
            f"{SITE_URL}categories/{category['id']}/",
        )
    ]
    parts.append(
        f"""<header><div class="wrap">
<a class="brand" href="../../">食品コスパ比較</a>
<h1>{category["emoji"]} {category["name"]}を{category["primary_label"]}で比較</h1>
<p class="lead">{category["intro"]}</p>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST。最新価格は販売ページで確認してください。</p>
</div></header>
<nav class="nav"><div class="wrap">
<a href="#included">送料込み比較</a>
<a href="#other">送料別参考</a>
<a href="../../">トップ</a>
</div></nav>
<main class="wrap">"""
    )
    parts.append(
        '<div id="included">'
        + comparison_table(
            included,
            category,
            f"送料込みで比べられる{category['name']}",
            f"{category['primary_label']}の安い順。送料込み確認済みの商品だけを順位付けしています。",
        )
        + "</div>"
    )
    parts.append(
        '<div id="other">'
        + comparison_table(
            other,
            category,
            "送料別・送料条件が別途ある商品",
            "単価は商品価格だけの参考値です。送料額は推測せず、送料込みランキングと混ぜません。",
        )
        + "</div>"
    )
    parts.append(
        """<section class="section explain">
<strong>比較ルール</strong>
<p>数量を安全に読み取れる商品だけを掲載し、定期購入・初回限定などは通常価格ランキングから除外します。クーポン・ポイントは通常単価へ差し引きません。</p>
</section></main>"""
    )
    parts.append(
        f"""<script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。価格は取得時点の参考情報です。</div></footer>
</body></html>"""
    )
    return "".join(parts)


def home_page(results: dict, updated: datetime) -> str:
    parts = [
        page_head(
            "食品コスパ比較｜容量・数量・送料をそろえて単価比較",
            "米、パックご飯、炭酸水、オートミールを1kg・1L・1食・100gあたりへ換算し、送料条件を分けて比較します。",
            SITE_URL,
        )
    ]
    parts.append(
        f"""<header><div class="wrap">
<span class="brand">FOOD COST</span>
<h1>食品は「いくら」より<br>「1単位いくら」で比べる。</h1>
<p class="lead">容量・本数・食数・セット数をそろえ、送料込みで比べられる商品を先に表示します。</p>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST</p>
</div></header>
<main class="wrap"><section class="grid">"""
    )
    for category in CATEGORIES:
        included, _ = results[category["id"]]
        best = included[0]["unit_prices"][category["primary"]] if included else None
        message = (
            f"取得商品では {category['primary_label']} {yen(best)}〜"
            if best is not None else "比較データを準備中"
        )
        parts.append(
            f"""<a class="card" href="categories/{category['id']}/">
<strong>{category['emoji']} {category['name']}</strong>
<p>{html.escape(message)}<br>{html.escape(category['intro'])}</p>
</a>"""
        )
    parts.append(
        """</section>
<section class="section explain">
<strong>このサイトの比較ルール</strong>
<p>送料込み確認済みを主ランキングにし、送料別は別枠。容量・数量が曖昧な商品は無理に計算しません。定期便・初回限定価格も通常ランキングへ混ぜません。</p>
</section></main>"""
    )
    parts.append(
        f"""<script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。</div></footer>
</body></html>"""
    )
    return "".join(parts)


def main():
    if not APP_ID or not ACCESS_KEY:
        raise SystemExit("RAKUTEN_APPLICATION_ID and RAKUTEN_ACCESS_KEY are required")

    OUT.mkdir(parents=True, exist_ok=True)
    updated = datetime.now(ZoneInfo("Asia/Tokyo"))
    results = {}
    export = {"generated_at": updated.isoformat(), "categories": {}}

    for category in CATEGORIES:
        included, other = collect(category)
        results[category["id"]] = (included, other)
        export["categories"][category["id"]] = {
            "included": included,
            "shipping_unknown": other,
        }

        target = OUT / "categories" / category["id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(
            category_page(category, included, other, updated),
            encoding="utf-8",
        )
        print(category["id"], len(included), len(other))

    (OUT / "index.html").write_text(home_page(results, updated), encoding="utf-8")
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "products.json").write_text(
        json.dumps(export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )

    urls = [SITE_URL] + [
        f"{SITE_URL}categories/{category['id']}/"
        for category in CATEGORIES
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(
            f"<url><loc>{url}</loc><lastmod>{updated:%Y-%m-%d}</lastmod></url>"
            for url in urls
        )
        + "</urlset>"
    )
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")


if __name__ == "__main__":
    main()
