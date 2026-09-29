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
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from product_display import clean_display_name
from product_quality import (
    category_rejection,
    product_fingerprint,
    quantity_conflict,
    quantity_signature,
)

SITE_ID = "food_cost_jp"
SITE_URL = "https://stusaurus.github.io/food-cost-jp/"
API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
OUT = Path("site")
APP_ID = os.getenv("RAKUTEN_APPLICATION_ID", "").strip()
ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()
GA_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()

CATEGORIES = [
    {"id":"pack-rice","name":"パックご飯","emoji":"🍚","queries":["パックご飯 200g","パックご飯 180g"],"primary":"per_serving","primary_label":"1食あたり","secondary":"per_100g","secondary_label":"100gあたり","intro":"食数と内容量をそろえ、24食・40食などの箱違いを公平に比較します。","filter_small":"24食以下","filter_large":"25食以上","guide":["1食あたりだけでなく、1食のグラム数も確認すると実際の満足度を比べやすくなります。","40食・80食などの大箱は単価が下がりやすい一方、保管場所も必要です。","容量や食数を一意に確定できない選択式商品はランキングから外しています。"]},
    {"id":"rice","name":"米","emoji":"🌾","queries":["米 5kg 送料無料","米 10kg 送料無料"],"primary":"per_kg","primary_label":"1kgあたり","secondary":None,"secondary_label":None,"intro":"5kg・10kgなど総重量が違う商品を1kgあたりへ換算します。","filter_small":"5kg以下","filter_large":"5kg超","guide":["5kgと10kgでは商品価格より1kgあたりを見ると比較しやすくなります。","銘柄・産年・精米方法は価格差の理由になるため、商品名の情報はできるだけ残しています。","5kg／10kg／20kgなど購入量が選択式で確定できない商品は除外しています。"]},
    {"id":"carbonated-water","name":"炭酸水","emoji":"🫧","queries":["炭酸水 500ml 24本","炭酸水 500ml 48本","炭酸水 1L"],"primary":"per_liter","primary_label":"1Lあたり","secondary":"per_bottle","secondary_label":"1本あたり","intro":"500ml・1L・24本・48本などを1Lあたりと1本あたりへ換算します。","filter_small":"600ml以下","filter_large":"700ml以上","guide":["持ち歩き中心なら1本あたり、自宅利用なら1Lあたりの単価を見ると選びやすくなります。","24本×2ケースなど明確な箱数は合計本数へ換算して比較します。","通常のミネラルウォーターや炭酸メーカー用品は炭酸水ランキングへ混ぜません。"]},
    {"id":"oatmeal","name":"オートミール","emoji":"🥣","queries":["オートミール 1kg","オートミール 2kg"],"primary":"per_100g","primary_label":"100gあたり","secondary":"per_kg","secondary_label":"1kgあたり","intro":"1kg袋・複数袋セットを100gあたりと1kgあたりへ換算します。","filter_small":"1kg以下","filter_large":"1kg超","guide":["袋サイズが違っても100gあたりへ換算すると価格差を比較しやすくなります。","複数袋セットは総重量へ換算し、セット数が曖昧な商品は除外しています。","ロールドオーツ・クイックオーツなどタイプは商品名で確認できるよう残しています。"]},
]

LIMITED_RE = re.compile(r"(?:定期購入(?:のみ)?|定期便(?:のみ)?|初回限定|会員限定|新規限定)")
PROMO_RE = re.compile(r"(?:クーポン|セール|SALE|タイムセール|ポイント\s*\d+倍|お買い物マラソン)", re.I)
SELECTABLE_RE = re.compile(r"(?:(?:容量|サイズ|個数|数量|本数|袋数|食数|セット数|重量|内容量)を?選択|\d+\s*(?:kg|g|ml|L)\s*[~/〜～-]\s*\d+)", re.I)


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
        nested = list(re.finditer(
            r"(\d+(?:\.\d+)?)\s*g\s*x\s*(\d+)\s*(?:食|個|パック)\s*\)?\s*x\s*(\d+)\s*(?:袋|箱|ケース|セット)",
            text,
            re.I,
        ))
        if nested:
            signatures = {
                (float(m.group(1)), int(m.group(2)), int(m.group(3)))
                for m in nested
            }
            if len(signatures) != 1:
                return None
            grams, inner_count, outer_count = next(iter(signatures))
            count = inner_count * outer_count
            if grams <= 0 or count <= 0:
                return None
            return {
                "total_weight_g": grams * count,
                "unit_weight_g": grams,
                "count": count,
                "component_counts": [inner_count, outer_count],
                "confidence": 0.997,
                "evidence": nested[0].group(0),
            }

        direct = list(re.finditer(
            r"(\d+(?:\.\d+)?)\s*g\s*[)）\]』】]*\s*x?\s*(\d+)\s*(?:食|個|パック)",
            text,
            re.I,
        ))
        direct_signatures = {(float(m.group(1)), int(m.group(2))) for m in direct}
        if len(direct_signatures) == 1:
            grams, count = next(iter(direct_signatures))
            if grams > 0 and count > 0:
                return {
                    "total_weight_g": grams * count,
                    "unit_weight_g": grams,
                    "count": count,
                    "confidence": 0.96,
                    "evidence": direct[0].group(0),
                }

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

            # For rice, reject listing titles that advertise additional package
            # sizes inconsistent with the explicit pack relation. Example:
            # "5kg×2袋 ... 10kg 20kg 27kg" is a size-selection page, not a
            # safely fixed 10kg listing.
            if category_id == "rice":
                total = amount * count
                allowed = {round(amount, 3), round(total, 3)}
                for wm in re.finditer(
                    r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(kg|g)",
                    text,
                    re.I,
                ):
                    grams = float(wm.group(1)) * (1000 if wm.group(2).lower() == "kg" else 1)
                    suffix = text[wm.end():wm.end() + 8]
                    if re.match(r"\s*(?:当り|あたり|当たり)", suffix):
                        continue
                    if round(grams, 3) not in allowed:
                        return None

            return {
                "total_weight_g": amount * count,
                "unit_weight_g": amount,
                "count": count,
                "confidence": 0.99,
                "evidence": m.group(0),
            }

        adjacent = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(kg|g)\s+(\d+)\s*(?:袋|個|パック)(?!以上)(?:セット)?",
            text,
            re.I,
        ))
        if adjacent:
            signatures = {(m.group(1), m.group(2).lower(), m.group(3)) for m in adjacent}
            if len(signatures) != 1:
                return None
            m = adjacent[0]
            amount = float(m.group(1)) * (1000 if m.group(2).lower() == "kg" else 1)
            count = int(m.group(3))
            if amount <= 0 or count <= 0:
                return None
            return {
                "total_weight_g": amount * count,
                "unit_weight_g": amount,
                "count": count,
                "confidence": 0.95,
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
        nested = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(ml|l)\s*x\s*(\d+)\s*(?:本|個|缶|パック)\s*x\s*(\d+)\s*(?:ケース|箱|セット)",
            text,
            re.I,
        ))
        if nested:
            signatures = {
                (m.group(1), m.group(2).lower(), m.group(3), m.group(4))
                for m in nested
            }
            if len(signatures) != 1:
                return None
            m = nested[0]
            amount = float(m.group(1)) * (1000 if m.group(2).lower() == "l" else 1)
            count = int(m.group(3)) * int(m.group(4))
            if amount <= 0 or count <= 0:
                return None
            return {
                "total_volume_ml": amount * count,
                "unit_volume_ml": amount,
                "count": count,
                "component_counts": [int(m.group(3)), int(m.group(4))],
                "confidence": 0.997,
                "evidence": m.group(0),
            }

        direct = list(re.finditer(
            r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(ml|l)\s*x?\s*(\d+)\s*(?:本|個|缶)",
            text,
            re.I,
        ))
        direct_signatures = {(m.group(1), m.group(2).lower(), m.group(3)) for m in direct}
        if len(direct_signatures) == 1:
            m = direct[0]
            amount = float(m.group(1)) * (1000 if m.group(2).lower() == "l" else 1)
            count = int(m.group(3))
            if amount > 0 and count > 0:
                return {
                    "total_volume_ml": amount * count,
                    "unit_volume_ml": amount,
                    "count": count,
                    "confidence": 0.96,
                    "evidence": m.group(0),
                }

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


def normalize_item_with_reason(raw: dict, category: dict):
    item = raw.get("Item", raw) if isinstance(raw, dict) else {}
    raw_name = str(item.get("itemName") or "").strip()
    try:
        price = int(float(item.get("itemPrice") or 0))
    except (TypeError, ValueError):
        return None, "invalid_price"

    if not raw_name:
        return None, "missing_title"
    if price <= 0:
        return None, "invalid_price"
    if LIMITED_RE.search(norm(raw_name)):
        return None, "limited_purchase"

    category_reason = category_rejection(category["id"], raw_name)
    if category_reason:
        return None, category_reason

    quantity = parse_quantity(raw_name, category["id"])
    if not quantity or quantity.get("confidence", 0) < 0.90:
        return None, "ambiguous_quantity"
    if quantity_conflict(raw_name, category["id"], quantity):
        return None, "set_count_conflict"

    prices = unit_prices(price, quantity, category["id"])
    if category["primary"] not in prices:
        return None, "unit_price_unavailable"

    postage_included = str(item.get("postageFlag")) == "0"
    url = str(item.get("affiliateUrl") or item.get("itemUrl") or "")
    if not url:
        return None, "missing_url"

    display_name = clean_display_name(raw_name)
    return {
        "id": str(item.get("itemCode") or url)[:180],
        "raw_name": raw_name,
        "name": display_name,
        "price": price,
        "shop": str(item.get("shopName") or ""),
        "url": url,
        "image": first_image(item),
        "postage_included": postage_included,
        "shipping_status": "included" if postage_included else "extra_or_unknown",
        "quantity": quantity,
        "unit_prices": prices,
        "promotion_mentioned": bool(PROMO_RE.search(norm(raw_name))),
    }, None


def normalize_item(raw: dict, category: dict):
    item, _ = normalize_item_with_reason(raw, category)
    return item


def collect(category: dict):
    rows = []
    for index, query in enumerate(category["queries"]):
        if index:
            time.sleep(1.1)
        try:
            rows.extend(fetch(query))
        except Exception as exc:
            print(f"fetch failed {category['id']} {query}: {exc}", file=sys.stderr)

    reasons = Counter()
    rejection_samples = {}
    cleaned_examples = []
    normalized = []
    for row in rows:
        item, reason = normalize_item_with_reason(row, category)
        if reason:
            reasons[reason] += 1
            raw = row.get("Item", row) if isinstance(row, dict) else {}
            title = str(raw.get("itemName") or "").strip()
            rejection_samples.setdefault(reason, [])
            if title and len(rejection_samples[reason]) < 3:
                rejection_samples[reason].append(title)
            continue
        if item["raw_name"] != item["name"] and len(cleaned_examples) < 12:
            cleaned_examples.append({
                "before": item["raw_name"],
                "after": item["name"],
            })
        normalized.append(item)

    # Query overlap: same Rakuten listing may be returned by multiple search terms.
    exact_seen = set()
    exact_unique = []
    exact_duplicates = 0
    for item in normalized:
        key = (item["id"], item["price"])
        if key in exact_seen:
            exact_duplicates += 1
            continue
        exact_seen.add(key)
        exact_unique.append(item)

    # Practical duplicates: same shop + cleaned product identity + same parsed
    # quantity. Keep the cheaper listing; do not merge across different shops.
    practical_seen = set()
    unique = []
    practical_duplicates = 0
    for item in sorted(exact_unique, key=lambda x: (x["price"], x["id"])):
        fingerprint = product_fingerprint(item["name"])
        pkey = (
            item["shop"].strip().lower(),
            fingerprint,
            quantity_signature(category["id"], item["quantity"]),
            item["shipping_status"],
        )
        if fingerprint and pkey in practical_seen:
            practical_duplicates += 1
            continue
        practical_seen.add(pkey)
        unique.append(item)

    sort_key = lambda item: (
        item["unit_prices"][category["primary"]],
        item["price"],
    )
    included_all = sorted([x for x in unique if x["postage_included"]], key=sort_key)
    other_all = sorted([x for x in unique if not x["postage_included"]], key=sort_key)
    included = included_all[:30]
    other = other_all[:20]

    audit = {
        "fetched": len(rows),
        "normalized": len(normalized),
        "exact_duplicates": exact_duplicates,
        "practical_duplicates": practical_duplicates,
        "accepted_unique": len(unique),
        "included_available": len(included_all),
        "shipping_unknown_available": len(other_all),
        "displayed_included": len(included),
        "displayed_shipping_unknown": len(other),
        "reasons": dict(reasons),
        "cleaned_examples": cleaned_examples,
        "rejection_samples": rejection_samples,
    }
    return included, other, audit

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
:root{--bg:#f5f7f4;--panel:#fff;--ink:#18201b;--muted:#657068;--line:#dfe6e0;--brand:#176a43;--brand-soft:#eaf5ee;--warm:#fff4df;--warm-ink:#855a16}
html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.65}
a{color:inherit}.wrap{width:min(1080px,calc(100% - 28px));margin:auto}
header{background:linear-gradient(180deg,#fff 0%,#f8fbf8 100%);border-bottom:1px solid var(--line);padding:30px 0 24px}
.brand{font-size:12px;font-weight:900;letter-spacing:.08em;color:var(--brand);text-decoration:none}
h1{font-size:clamp(28px,7vw,46px);line-height:1.18;margin:8px 0 12px}h2{font-size:clamp(21px,4vw,28px);line-height:1.35}
.lead{font-size:clamp(15px,2.4vw,18px);max-width:760px}.lead,.sub,.note{color:var(--muted)}.note{font-size:12px}
.hero-tags{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0 6px}.hero-tag{font-size:11px;font-weight:800;background:var(--brand-soft);color:var(--brand);border-radius:999px;padding:5px 9px}
.nav{position:sticky;top:0;background:#ffffffed;border-bottom:1px solid var(--line);z-index:10;backdrop-filter:blur(10px)}
.nav .wrap{display:flex;gap:8px;overflow:auto;padding:9px 14px}.nav a{white-space:nowrap;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:#fff;font-size:12px;font-weight:700}
.grid{display:grid;gap:12px;margin:22px 0}.card,.explain,.summary{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;text-decoration:none}
.category-card{display:block;position:relative;transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease}.category-card:hover{transform:translateY(-2px);border-color:#bfd2c5;box-shadow:0 8px 24px #1d442b12}
.category-name{font-size:18px;font-weight:900}.category-price{font-size:26px;line-height:1.15;color:var(--brand);font-weight:950;margin:9px 0 2px}.category-meta{font-size:12px;color:var(--muted)}.category-go{display:inline-block;margin-top:10px;font-size:12px;font-weight:900;color:var(--brand)}
.section{margin:30px 0 46px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.toolbar select,.toolbar input{min-height:42px;border:1px solid var(--line);border-radius:11px;background:#fff;padding:0 11px;font-weight:700}.toolbar input{flex:1;min-width:220px}.toolbar input::placeholder{color:#88928c;font-weight:600}
.summary{margin:20px 0 12px}.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.summary-item{background:#f7faf7;border-radius:13px;padding:12px}.summary-k{font-size:11px;color:var(--muted);font-weight:800}.summary-v{font-size:20px;font-weight:950;color:var(--brand);margin-top:2px}
.table{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:16px}table{border-collapse:collapse;width:100%;min-width:800px}
th,td{padding:11px;border-bottom:1px solid #e8ece8;text-align:left;font-size:12px;vertical-align:top}th{background:#f1f5f2;font-size:11px;color:#536058}
.product-name{display:block;font-size:13px;line-height:1.45}.shop{color:var(--muted);margin:4px 0 6px}.product-img{width:72px;height:72px;object-fit:contain;border-radius:10px;background:#fff}
.rank{font-size:15px;font-weight:950}.rank.top{display:inline-flex;width:29px;height:29px;align-items:center;justify-content:center;border-radius:50%;background:var(--brand);color:#fff}
.unit{font-size:20px;font-weight:950;color:var(--brand);white-space:nowrap}.unit-label{font-size:10px;color:var(--muted);font-weight:700}.secondary-unit{font-size:11px;color:#536058;margin-top:3px}
.tag{display:inline-block;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:800;margin:2px 2px 0 0}.ok{background:var(--brand-soft);color:var(--brand)}.warn{background:var(--warm);color:var(--warm-ink)}
.cta{display:inline-flex;justify-content:center;align-items:center;min-height:40px;padding:0 11px;border-radius:10px;background:var(--brand);color:#fff;text-decoration:none;font-weight:900;white-space:nowrap}
.guide-list{margin:10px 0 0;padding-left:20px}.guide-list li{margin:7px 0}.fine{font-size:11px;color:var(--muted)}.other-categories{display:flex;gap:8px;flex-wrap:wrap}.other-categories a{border:1px solid var(--line);background:#fff;border-radius:999px;padding:8px 11px;text-decoration:none;font-size:12px;font-weight:800}.empty-filter{display:none;background:#fff;border:1px dashed var(--line);border-radius:14px;padding:18px;color:var(--muted);text-align:center}
footer{background:#fff;border-top:1px solid var(--line);padding:30px 0 42px;color:var(--muted);font-size:11px}
@media(min-width:720px){.grid{grid-template-columns:1fr 1fr}}
@media(max-width:719px){
 .wrap{width:min(100% - 20px,1080px)}header{padding:24px 0 18px}.summary-grid{grid-template-columns:1fr 1fr}.summary-item:first-child{grid-column:1/-1}
 .table{overflow:visible;background:transparent;border:0}table,tbody{display:block;width:100%;min-width:0}thead{display:none}tr{display:grid;grid-template-columns:76px 1fr;gap:0 12px;background:#fff;border:1px solid var(--line);border-radius:16px;margin:10px 0;padding:13px;box-shadow:0 2px 8px #13291b08}
 td{display:block;border:0;padding:3px 0;font-size:12px;min-width:0}td[data-cell="rank"]{grid-column:1/-1;padding-bottom:5px}td[data-cell="image"]{grid-column:1;grid-row:2 / span 4}td[data-cell="product"],td[data-cell="quantity"],td[data-cell="price"],td[data-cell="unit"],td[data-cell="cta"]{grid-column:2}
 td[data-cell="product"]{padding-top:0}.product-img{width:72px;height:72px}.product-name{font-size:14px}.unit{font-size:23px;margin-top:3px}td[data-cell="quantity"]::before{content:"内容量  ";font-weight:800;color:var(--muted)}td[data-cell="price"]::before{content:"商品価格  ";font-weight:800;color:var(--muted)}
 td[data-cell="cta"]{margin-top:8px}.cta{width:100%;min-height:46px}.toolbar select,.toolbar input{flex:1;min-width:0;width:100%}.section{margin:24px 0 36px}
}"""


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
const applyFilters=root=>{
  const size=root.querySelector('[data-filter]')?.value||'all';
  const term=(root.querySelector('[data-search]')?.value||'').trim().toLowerCase();
  let shown=0;
  root.querySelectorAll('tbody tr').forEach(r=>{
    const sizeOk=size==='all'||r.dataset.bucket===size;
    const textOk=!term||(r.dataset.searchText||'').includes(term);
    r.hidden=!(sizeOk&&textOk);
    if(!r.hidden)shown++;
  });
  const empty=root.querySelector('[data-empty-filter]');
  if(empty)empty.style.display=shown?'none':'block';
};
document.querySelectorAll('[data-filter]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]');applyFilters(root);
  send('comparison_filter_use',{category_id:s.dataset.category,filter_value:s.value})
}));
document.querySelectorAll('[data-search]').forEach(input=>input.addEventListener('change',()=>{
  const root=input.closest('[data-comparison]');applyFilters(root);
  send('comparison_search_use',{category_id:input.dataset.category,search_term:input.value.trim()})
}));
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
            f'<div class="secondary-unit">{html.escape(category["secondary_label"])} {yen(item["unit_prices"].get(secondary_metric))}</div>'
            if secondary_metric else ""
        )
        image = (
            f'<img class="product-img" src="{html.escape(item["image"], quote=True)}" alt="" width="72" height="72" loading="lazy">'
            if item["image"] else ""
        )
        shipping = '<span class="tag ok">送料込み</span>' if item["postage_included"] else '<span class="tag warn">送料別・要確認</span>'
        promo = '<span class="tag warn">セール/クーポン表記</span>' if item["promotion_mentioned"] else ""
        attrs = f'data-price="{item["price"]}" ' + " ".join(
            f'data-{key}="{value:.6f}"'
            for key, value in item["unit_prices"].items()
        )
        rank_html = f'<span class="rank top">{rank}</span>' if rank <= 3 else f'<span class="rank">{rank}</span>'
        search_text = html.escape((item["name"] + " " + item["shop"]).lower(), quote=True)
        rows.append(
            f"""<tr data-bucket="{bucket(item, category['id'])}" data-search-text="{search_text}" {attrs}>
<td data-cell="rank" data-rank>{rank_html}</td>
<td data-cell="image">{image}</td>
<td data-cell="product"><strong class="product-name">{html.escape(item['name'])}</strong><div class="shop">{html.escape(item['shop'])}</div>{shipping} {promo}</td>
<td data-cell="quantity">{html.escape(quantity_text(item, category['id']))}</td>
<td data-cell="price">¥{item['price']:,}</td>
<td data-cell="unit"><div class="unit">{yen(primary)}</div><div class="unit-label">{html.escape(category['primary_label'])}</div>{secondary}</td>
<td data-cell="cta"><a class="cta" href="{html.escape(item['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{primary_metric}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}">楽天で価格を見る →</a></td>
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
<input type="search" data-search data-category="{category['id']}" placeholder="商品名・ショップ名で絞る" aria-label="{html.escape(category['name'])}の商品名・ショップ名で絞る">
<select data-sort data-category="{category['id']}">{''.join(options)}</select>
<select data-filter data-category="{category['id']}">
<option value="all">容量・数量すべて</option>
<option value="small">{html.escape(category['filter_small'])}</option>
<option value="large">{html.escape(category['filter_large'])}</option>
</select>
</div>
<div class="empty-filter" data-empty-filter>条件に合う商品がありません。検索語や容量条件を変えてください。</div>
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


def category_summary(category: dict, included: list[dict], other: list[dict]) -> str:
    all_items = included + other
    if not all_items:
        return ""
    primary = category["primary"]
    best = included[0]["unit_prices"][primary] if included else min(x["unit_prices"][primary] for x in all_items)
    return f"""<section class="summary" aria-label="比較サマリー">
<div class="summary-grid">
<div class="summary-item"><div class="summary-k">送料込み最安</div><div class="summary-v">{yen(best)}</div><div class="fine">{html.escape(category['primary_label'])}</div></div>
<div class="summary-item"><div class="summary-k">送料込み掲載</div><div class="summary-v">{len(included)}件</div></div>
<div class="summary-item"><div class="summary-k">送料別参考</div><div class="summary-v">{len(other)}件</div></div>
</div></section>"""


def guide_html(category: dict) -> str:
    points = "".join(f"<li>{html.escape(point)}</li>" for point in category["guide"])
    return f"""<section class="section explain">
<h2>{category['emoji']} {html.escape(category['name'])}を比べるコツ</h2>
<ul class="guide-list">{points}</ul>
</section>"""


def other_categories_html(current_id: str) -> str:
    links = "".join(
        f'<a href="../{category["id"]}/">{category["emoji"]} {html.escape(category["name"])}</a>'
        for category in CATEGORIES
        if category["id"] != current_id
    )
    return f"""<section class="section">
<h2>ほかの食品も単価で比べる</h2>
<div class="other-categories">{links}</div>
</section>"""


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
<div class="hero-tags"><span class="hero-tag">送料込みを優先</span><span class="hero-tag">数量曖昧は除外</span><span class="hero-tag">クーポン未反映</span></div>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST。最新価格は販売ページで確認してください。</p>
</div></header>
<nav class="nav"><div class="wrap">
<a href="#included">送料込み比較</a>
<a href="#other">送料別参考</a>
<a href="../../">トップ</a>
</div></nav>
<main class="wrap">"""
    )
    parts.append(category_summary(category, included, other))
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
    parts.append(guide_html(category))
    parts.append(other_categories_html(category["id"]))
    parts.append(
        """<section class="section explain">
<h2>このランキングのルール</h2>
<p>数量を安全に読み取れる商品だけを掲載し、定期購入・初回限定などは通常価格ランキングから除外します。クーポン・ポイントは通常単価へ差し引きません。</p>
<p class="fine">送料込みは楽天APIの送料フラグを基準にし、地域別の追加送料などは販売ページで最終確認してください。</p>
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
<p class="lead">容量・本数・食数・セット数をそろえて、同じものさしで比較。商品価格だけでは見えにくい「本当に安い」を探せます。</p>
<div class="hero-tags"><span class="hero-tag">送料込みを優先</span><span class="hero-tag">数量曖昧は除外</span><span class="hero-tag">毎回楽天から再取得</span></div>
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
            f"""<a class="card category-card" href="categories/{category['id']}/">
<div class="category-name">{category['emoji']} {category['name']}</div>
<div class="category-price">{html.escape(message.replace('取得商品では ', ''))}</div>
<div class="category-meta">送料込み {len(included)}件を比較中</div>
<p>{html.escape(category['intro'])}</p>
<span class="category-go">ランキングを見る →</span>
</a>"""
        )
    parts.append(
        """</section>
<section class="section explain">
<h2>このサイトの比較ルール</h2>
<p>送料込み確認済みを主ランキングにし、送料別は別枠。容量・数量が曖昧な商品は無理に計算しません。定期便・初回限定価格も通常ランキングへ混ぜません。</p>
<ul class="guide-list">
<li>容量やセット数を同じ単位に換算して比較</li>
<li>クーポンやポイントは通常単価へ勝手に差し引かない</li>
<li>販売数量を一意に確定できない商品はランキングから除外</li>
</ul>
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
        included, other, audit = collect(category)
        results[category["id"]] = (included, other)
        export["categories"][category["id"]] = {
            "included": included,
            "shipping_unknown": other,
            "quality_audit": {
                key: value
                for key, value in audit.items()
                if key not in {"cleaned_examples", "rejection_samples"}
            },
        }

        target = OUT / "categories" / category["id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(
            category_page(category, included, other, updated),
            encoding="utf-8",
        )
        print(category["id"], len(included), len(other))
        print(
            "AUDIT",
            category["id"],
            json.dumps({
                key: value
                for key, value in audit.items()
                if key not in {"cleaned_examples", "rejection_samples"}
            }, ensure_ascii=False, sort_keys=True),
        )
        for example in audit["cleaned_examples"]:
            print(
                "CLEANED",
                category["id"],
                json.dumps(example, ensure_ascii=False),
            )
        for reason, samples in sorted(audit["rejection_samples"].items()):
            for sample in samples:
                print(
                    "EXCLUDE",
                    category["id"],
                    reason,
                    json.dumps(sample, ensure_ascii=False),
                )

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
