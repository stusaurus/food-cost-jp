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

GUIDE_SPECS = [
    {"slug":"pack-rice-200g-cost","category_id":"pack-rice","title":"パックご飯200g前後のコスパ比較","h1":"パックご飯200g前後を1食あたりで比較","intro":"180〜210g前後のパックご飯から、送料込みで比較できる商品を1食あたりの単価で見ます。","mode":"pack_200"},
    {"slug":"pack-rice-bulk-cost","category_id":"pack-rice","title":"パックご飯まとめ買いのコスパ比較","h1":"パックご飯の大箱・まとめ買いを比較","intro":"25食以上のまとめ買い向け商品を中心に、1食あたりの単価と総額を比べます。","mode":"large"},
    {"slug":"rice-5kg-cost","category_id":"rice","title":"米5kgのコスパ比較","h1":"米5kg前後を1kgあたりで比較","intro":"5kg前後の米を送料込みでそろえ、商品価格だけでなく1kgあたりの単価で比べます。","mode":"rice_5kg"},
    {"slug":"rice-10kg-cost","category_id":"rice","title":"米10kgのコスパ比較","h1":"米10kg前後を1kgあたりで比較","intro":"10kg前後の米を1kgあたりへ換算し、まとめ買い時の価格差を見やすくします。","mode":"rice_10kg"},
    {"slug":"carbonated-water-24-cost","category_id":"carbonated-water","title":"炭酸水24本のコスパ比較","h1":"炭酸水24本を1L・1本あたりで比較","intro":"24本セットの炭酸水を中心に、1Lあたりと1本あたりの両方で比べます。","mode":"count_24"},
    {"slug":"carbonated-water-48-cost","category_id":"carbonated-water","title":"炭酸水48本のコスパ比較","h1":"炭酸水48本を1L・1本あたりで比較","intro":"48本前後の大容量セットを中心に、まとめ買い時の単価を比べます。","mode":"count_48"},
    {"slug":"oatmeal-1kg-cost","category_id":"oatmeal","title":"オートミール1kgのコスパ比較","h1":"オートミール1kg前後を100gあたりで比較","intro":"1kg前後のオートミールを100gあたりへ換算し、袋価格だけでは分からない差を比べます。","mode":"oats_1kg"},
    {"slug":"oatmeal-bulk-cost","category_id":"oatmeal","title":"オートミール大容量のコスパ比較","h1":"オートミール大容量・まとめ買いを比較","intro":"1kg超の大容量商品を中心に、100gあたり・1kgあたりの単価を比べます。","mode":"large"},
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


def category_illustration(category_id: str, compact: bool = False) -> str:
    """Inline SVG illustrations: original, lightweight, and dependency-free."""
    common = 'viewBox="0 0 240 180" role="img" aria-hidden="true" focusable="false"'
    if category_id == "rice":
        art = f"""<svg {common} class="food-art" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="122" cy="151" rx="78" ry="12" fill="#000" opacity=".06"/>
<path d="M67 45h94l13 99H54L67 45Z" fill="#FFF8DE" stroke="#8A7130" stroke-width="5"/>
<path d="M73 45c8-18 74-18 82 0" fill="#F1D978" stroke="#8A7130" stroke-width="5"/>
<path d="M91 92c18-21 44-21 62 0-16 11-47 11-62 0Z" fill="#fff" stroke="#8A7130" stroke-width="4"/>
<path d="M122 69c-8 13-12 24-10 34M125 68c8 13 12 24 10 34" stroke="#84A657" stroke-width="4" stroke-linecap="round"/>
<text x="120" y="126" text-anchor="middle" font-size="18" font-weight="800" fill="#66531F">おこめ</text>
<circle cx="48" cy="65" r="11" fill="#D8E8B5"/><circle cx="183" cy="75" r="8" fill="#F2D870"/>
</svg>"""
    elif category_id == "pack-rice":
        art = f"""<svg {common} class="food-art" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="121" cy="151" rx="82" ry="12" fill="#000" opacity=".06"/>
<rect x="48" y="72" width="144" height="70" rx="18" fill="#FFF0DD" stroke="#B8793D" stroke-width="5"/>
<rect x="61" y="54" width="118" height="39" rx="14" fill="#fff" stroke="#B8793D" stroke-width="5"/>
<path d="M75 79c16-24 73-24 91 0" fill="#fff" stroke="#D4B08B" stroke-width="4"/>
<circle cx="91" cy="71" r="5" fill="#F0E5D8"/><circle cx="113" cy="64" r="5" fill="#F0E5D8"/><circle cx="137" cy="69" r="5" fill="#F0E5D8"/><circle cx="154" cy="76" r="4" fill="#F0E5D8"/>
<path d="M79 111h82" stroke="#E3B87F" stroke-width="6" stroke-linecap="round"/>
<path d="M85 126h58" stroke="#E3B87F" stroke-width="6" stroke-linecap="round"/>
<path d="M183 37c11 9 11 20 0 29M198 28c14 13 14 31 0 44" fill="none" stroke="#F2B56E" stroke-width="5" stroke-linecap="round"/>
</svg>"""
    elif category_id == "carbonated-water":
        art = f"""<svg {common} class="food-art" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="120" cy="154" rx="72" ry="10" fill="#000" opacity=".06"/>
<path d="M89 51h52l9 91c1 8-5 14-13 14H93c-8 0-14-6-13-14l9-91Z" fill="#DCF7FF" stroke="#4C9CB8" stroke-width="5"/>
<rect x="96" y="30" width="38" height="28" rx="8" fill="#8AD5EA" stroke="#4C9CB8" stroke-width="5"/>
<rect x="95" y="82" width="48" height="38" rx="12" fill="#fff" opacity=".8"/>
<circle cx="109" cy="101" r="7" fill="#7ED5EF"/><circle cx="129" cy="94" r="5" fill="#7ED5EF"/><circle cx="124" cy="113" r="4" fill="#7ED5EF"/>
<circle cx="171" cy="51" r="10" fill="#B9ECFA"/><circle cx="188" cy="78" r="6" fill="#B9ECFA"/><circle cx="58" cy="73" r="8" fill="#B9ECFA"/>
</svg>"""
    else:
        art = f"""<svg {common} class="food-art" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="120" cy="151" rx="79" ry="11" fill="#000" opacity=".06"/>
<path d="M57 88h126c-5 42-25 62-63 62S62 130 57 88Z" fill="#F7E2C5" stroke="#9A7045" stroke-width="5"/>
<path d="M70 87c12-25 90-25 102 0" fill="#DDBB8B" stroke="#9A7045" stroke-width="5"/>
<ellipse cx="93" cy="79" rx="10" ry="6" fill="#F8EACF"/><ellipse cx="119" cy="74" rx="11" ry="6" fill="#F8EACF"/><ellipse cx="145" cy="80" rx="9" ry="5" fill="#F8EACF"/>
<path d="M164 34c-13 15-25 36-32 58" stroke="#717B61" stroke-width="7" stroke-linecap="round"/>
<circle cx="169" cy="30" r="8" fill="#A9B68E"/>
</svg>"""
    return art.replace('class="food-art"', 'class="food-art compact"') if compact else art


def hero_illustrations() -> str:
    items = "".join(
        f'<div class="hero-art-item {category["id"]}">{category_illustration(category["id"], True)}</div>'
        for category in CATEGORIES
    )
    return f'<div class="hero-art-grid" aria-hidden="true">{items}</div>'


def guide_mascot(compact: bool = False) -> str:
    cls = "guide-mascot compact" if compact else "guide-mascot"
    return f"""<svg class="{cls}" viewBox="0 0 300 260" role="img" aria-label="食品コスパ比較の案内役" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="150" cy="232" rx="92" ry="15" fill="#173F31" opacity=".08"/>
<path d="M69 91h153l-15 103c-2 14-14 24-28 24h-58c-14 0-26-10-28-24L69 91Z" fill="#F4D88A" stroke="#315A43" stroke-width="7"/>
<path d="M104 90c4-35 88-35 92 0" fill="none" stroke="#315A43" stroke-width="8" stroke-linecap="round"/>
<rect x="111" y="118" width="78" height="69" rx="14" fill="#FFFDF8" stroke="#315A43" stroke-width="6"/>
<rect x="126" y="132" width="48" height="15" rx="5" fill="#DDEDDC"/>
<circle cx="131" cy="163" r="6" fill="#6FA37E"/><circle cx="150" cy="163" r="6" fill="#6FA37E"/><circle cx="169" cy="163" r="6" fill="#6FA37E"/>
<circle cx="122" cy="104" r="6" fill="#315A43"/><circle cx="180" cy="104" r="6" fill="#315A43"/>
<path d="M139 108c6 8 16 8 22 0" fill="none" stroke="#315A43" stroke-width="5" stroke-linecap="round"/>
<circle cx="61" cy="55" r="24" fill="#DDF4E5"/><text x="61" y="63" text-anchor="middle" font-size="22">¥</text>
<circle cx="236" cy="56" r="25" fill="#DDF3FA"/><text x="236" y="64" text-anchor="middle" font-size="22">÷</text>
<path d="M82 61c14 7 21 16 25 27M216 63c-12 8-19 16-23 27" fill="none" stroke="#9EC4AA" stroke-width="4" stroke-linecap="round"/>
</svg>"""


def hero_visual() -> str:
    return f"""<div class="hero-visual" aria-hidden="true">
<div class="mascot-bubble">同じ単位にそろえて<br><strong>安い順にするよ</strong></div>
{guide_mascot()}
<div class="hero-food-chip chip-rice">🌾 1kg</div>
<div class="hero-food-chip chip-water">🫧 1L</div>
<div class="hero-food-chip chip-pack">🍚 1食</div>
<div class="hero-food-chip chip-oats">🥣 100g</div>
</div>"""


def finder_pick_items(items: list[dict], category: dict, purpose: str) -> list[dict]:
    source = list(items)
    if purpose == "small":
        picked = [x for x in source if bucket(x, category["id"]) == "small"]
    elif purpose == "large":
        picked = [x for x in source if bucket(x, category["id"]) == "large"]
    elif purpose == "budget":
        picked = sorted(source, key=lambda x: (x["price"], x["unit_prices"][category["primary"]]))
    elif purpose == "storage":
        picked = [x for x in source if bucket(x, category["id"]) == "small"]
        picked.sort(key=lambda x: (x["price"], x["unit_prices"][category["primary"]]))
    else:
        picked = source
    return picked[:3] if picked else source[:3]


def recommendation_reason(item: dict, category: dict, purpose: str, position: int) -> str:
    if purpose == "budget":
        return "支払総額を抑えやすい候補" if position == 1 else "商品価格が低めの候補"
    if purpose == "storage":
        return "保管しやすい少量側から選定" if position == 1 else "置き場所を取りにくい候補"
    if purpose == "small":
        return "少量側の中で単価が安い候補"
    if purpose == "large":
        return "大容量側の中で単価が安い候補"
    return "この条件で単価が安い候補" if position == 1 else "上位の高コスパ候補"


def finder_product_card(item: dict, category: dict, position: int, purpose: str) -> str:
    primary = item["unit_prices"][category["primary"]]
    image = (
        f'<img src="{html.escape(item["image"], quote=True)}" alt="" loading="lazy">'
        if item["image"] else category_illustration(category["id"], True)
    )
    reason = recommendation_reason(item, category, purpose, position)
    return f"""<article class="finder-product">
<div class="finder-product-media">{image}</div>
<div class="finder-product-copy">
<span class="finder-product-rank">{position}</span>
<strong>{html.escape(item["name"])}</strong>
<div class="finder-product-price">{yen(primary)} <small>{html.escape(category["primary_label"])}</small></div>
<div class="finder-product-meta">{html.escape(quantity_text(item, category["id"]))} ・ ¥{item["price"]:,}</div>
<div class="finder-why"><span>なぜ？</span>{html.escape(reason)}</div>
{product_action_buttons(item, category, primary)}
<a class="cta" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-position="quick_finder_result" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{position}" data-metric="{category['primary']}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}">楽天で確認 →</a>
</div></article>"""



def product_action_buttons(item: dict, category: dict, primary: float) -> str:
    quantity = quantity_text(item, category["id"])
    attrs = (
        f'data-product-id="{html.escape(item["id"], quote=True)}" '
        f'data-product-name="{html.escape(item["name"], quote=True)}" '
        f'data-product-category="{category["id"]}" '
        f'data-product-category-name="{html.escape(category["name"], quote=True)}" '
        f'data-product-price="{item["price"]}" '
        f'data-product-unit="{primary:.6f}" '
        f'data-product-unit-label="{html.escape(category["primary_label"], quote=True)}" '
        f'data-product-quantity="{html.escape(quantity, quote=True)}" '
        f'data-product-url="{html.escape(item["url"], quote=True)}" '
        f'data-product-image="{html.escape(item["image"] or "", quote=True)}"'
    )
    return f"""<div class="product-actions">
<button type="button" class="utility-btn" data-save-product {attrs}>♡ あとで見る</button>
<button type="button" class="utility-btn" data-compare-product {attrs}>＋ 比較する</button>
</div>"""


def category_insights_html(category: dict, items: list[dict]) -> str:
    if not items:
        return ""
    metric = category["primary"]
    ordered = sorted(items, key=lambda x: x["unit_prices"][metric])
    best = ordered[0]["unit_prices"][metric]
    third = ordered[min(2, len(ordered)-1)]["unit_prices"][metric]
    cheapest_total = min(items, key=lambda x: x["price"])
    large_items = [x for x in items if bucket(x, category["id"]) == "large"]
    large_best = min(large_items, key=lambda x: x["unit_prices"][metric]) if large_items else None
    diff = max(0, third - best)
    large_html = (
        f"""<div class="insight-card"><span>📦 大容量側の注目</span><strong>{yen(large_best["unit_prices"][metric])}</strong><small>{html.escape(category["primary_label"])}</small></div>"""
        if large_best else
        """<div class="insight-card"><span>📦 大容量側</span><strong>—</strong><small>現在候補なし</small></div>"""
    )
    return f"""<section class="section insight-section">
<div class="section-kicker">PRICE SNAPSHOT</div>
<h2>いまの価格差をひと目で。</h2>
<div class="insight-grid">
<div class="insight-card"><span>🥇 1位と3位の差</span><strong>{yen(diff)}</strong><small>{html.escape(category["primary_label"])}の差</small></div>
<div class="insight-card"><span>💴 支払総額が低い候補</span><strong>¥{cheapest_total["price"]:,}</strong><small>{html.escape(quantity_text(cheapest_total, category["id"]))}</small></div>
{large_html}
</div>
<p class="fine">単価だけでなく、支払総額や保管量も見て選べます。価格は取得時点の参考値です。</p>
</section>"""


def breadcrumb_json_ld(items: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": name, "item": url}
            for index, (name, url) in enumerate(items, start=1)
        ],
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'


def item_list_json_ld(items: list[dict], category: dict, limit: int = 10) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{category['name']}のコスパ比較",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": item["name"],
                "url": item["url"],
            }
            for index, item in enumerate(items[:limit], start=1)
        ],
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'


def utility_panels_html() -> str:
    return """<button class="saved-fab" type="button" data-open-saved>♡ あとで見る <span data-saved-count>0</span></button>
<div class="compare-bar" data-compare-bar hidden>
<div><strong>比較する商品</strong><span data-compare-summary>0/3</span></div>
<div class="compare-bar-items" data-compare-bar-items></div>
<button type="button" class="compare-open" data-open-compare>比較を見る</button>
<button type="button" class="compare-clear" data-clear-compare>クリア</button>
</div>
<div class="utility-modal" data-saved-modal hidden>
<div class="utility-sheet">
<button class="utility-close" type="button" data-close-saved>×</button>
<div class="section-kicker">SAVED</div><h2>あとで見る</h2>
<div data-saved-list></div>
</div></div>
<div class="site-toast" data-toast hidden></div>
<div class="utility-modal" data-compare-modal hidden>
<div class="utility-sheet utility-sheet-wide">
<button class="utility-close" type="button" data-close-compare>×</button>
<div class="section-kicker">COMPARE</div><h2>選んだ商品を比較</h2>
<div data-compare-table></div>
</div></div>"""



def top3_html(items: list[dict], category: dict) -> str:
    if not items:
        return ""
    cards = []
    labels = ["いまの最安", "2位", "3位"]
    medal = ["🥇", "🥈", "🥉"]
    best_primary = items[0]["unit_prices"][category["primary"]]
    for index, item in enumerate(items[:3]):
        rank = index + 1
        primary = item["unit_prices"][category["primary"]]
        diff = max(0, primary - best_primary)
        diff_text = "最安" if rank == 1 else f"最安との差 +{yen(diff)}"
        image = (
            f'<img class="podium-img" src="{html.escape(item["image"], quote=True)}" alt="" loading="lazy">'
            if item["image"] else category_illustration(category["id"], True)
        )
        cards.append(f"""<article class="podium-card rank-{rank}">
<div class="podium-head"><span class="podium-medal">{medal[index]}</span><span>{labels[index]}</span></div>
<div class="podium-badges">{item_badges(item, category, rank)}</div>
<div class="podium-media">{image}</div>
<strong class="podium-name">{html.escape(item["name"])}</strong>
<div class="podium-unit">{yen(primary)}</div>
<div class="podium-label">{html.escape(category["primary_label"])}</div>
<div class="podium-diff">{html.escape(diff_text)}</div>
<div class="podium-detail">{html.escape(quantity_text(item, category["id"]))} ・ ¥{item["price"]:,}</div>
{product_action_buttons(item, category, primary)}
<a class="cta podium-cta" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-position="top3_card" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{category['primary']}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}">楽天で確認する →</a>
</article>""")
    return f"""<section class="section podium-section">
<div class="section-kicker">まずはここから</div>
<h2>送料込み TOP{min(3, len(items))}</h2>
<p class="sub">現在取得できた商品の中で、{html.escape(category["primary_label"])}が安い順です。</p>
<div class="podium-grid">{''.join(cards)}</div>
</section>"""


def choice_finder_html(results: dict) -> str:
    choices = "".join(
        f"""<button class="finder-category {category['id']}" type="button"
 data-finder-category="{category['id']}" data-finder-name="{html.escape(category['name'], quote=True)}">
<span class="finder-art">{category_illustration(category['id'], True)}</span>
<span>{category['emoji']} {html.escape(category['name'])}</span>
</button>"""
        for category in CATEGORIES
    )
    labels = {"cheap": "単価重視", "small": "少量で買いたい", "large": "まとめ買い", "budget": "支払総額を抑える", "storage": "保管しやすさ重視"}
    panels = []
    for category in CATEGORIES:
        included, _ = results[category["id"]]
        for purpose in ("cheap", "small", "large", "budget", "storage"):
            picks = finder_pick_items(included, category, purpose)
            cards = "".join(
                finder_product_card(item, category, index, purpose)
                for index, item in enumerate(picks, start=1)
            )
            panels.append(f"""<div class="finder-picks" data-finder-picks="{category['id']}:{purpose}" hidden>
<div class="finder-picks-head"><span>あなた向け</span><strong>{category['emoji']} {html.escape(category['name'])} × {labels[purpose]}</strong></div>
<div class="finder-products">{cards}</div>
<a class="finder-all" href="categories/{category['id']}/?pick={purpose}#included">この条件の商品を全部見る →</a>
</div>""")
    return f"""<section class="section finder" data-finder>
<div class="finder-intro">
<div>
<div class="section-kicker">QUICK FINDER</div>
<h2>2回選ぶだけ。候補まで出します。</h2>
<p class="sub">食品と買い方を選ぶと、今の楽天データからおすすめ候補を表示します。</p>
</div>
<div class="finder-guide">{guide_mascot(True)}<span>選んでみて</span></div>
</div>
<div class="finder-stage" data-finder-category-stage>
<div class="finder-question"><span>Q1</span><strong>何を買う？</strong></div>
<div class="finder-options finder-category-options">{choices}</div>
</div>
<div class="finder-stage" data-finder-purpose-stage hidden>
<button class="finder-back" type="button" data-finder-back>← 食品を選び直す</button>
<div class="finder-question"><span>Q2</span><strong data-finder-question-title>どんな買い方？</strong></div>
<div class="finder-options finder-purpose-options">
<button type="button" data-finder-purpose="cheap">💰 <span><strong>単価重視</strong><small>とにかく安い順で</small></span></button>
<button type="button" data-finder-purpose="small">🧺 <span><strong>少量で</strong><small>置き場所・買いやすさ重視</small></span></button>
<button type="button" data-finder-purpose="large">📦 <span><strong>まとめ買い</strong><small>大容量から選ぶ</small></span></button>
<button type="button" data-finder-purpose="budget">💴 <span><strong>支払総額を抑える</strong><small>まず安く買える商品から</small></span></button>
<button type="button" data-finder-purpose="storage">🏠 <span><strong>保管しやすさ</strong><small>置き場所を取りにくい量から</small></span></button>
</div>
</div>
<div class="finder-stage finder-result-stage" data-finder-result-stage hidden>
<button class="finder-back" type="button" data-finder-reset>← もう一度選ぶ</button>
{''.join(panels)}
</div>
</section>"""

def item_badges(item: dict, category: dict, rank: int) -> str:
    badges = []
    if rank == 1 and item["postage_included"]:
        badges.append('<span class="tag best">👑 最安候補</span>')
    elif rank <= 3 and item["postage_included"]:
        badges.append('<span class="tag top-badge">TOP3</span>')
    size = bucket(item, category["id"])
    if size == "small":
        badges.append('<span class="tag lifestyle">少量向き</span>')
    elif size == "large":
        badges.append('<span class="tag lifestyle">まとめ買い向き</span>')
    return " ".join(badges)


def comparison_flow_html() -> str:
    return """<section class="section flow-section">
<div class="section-kicker">HOW IT WORKS</div>
<h2>値札だけでは分からない「本当の安さ」を3ステップで。</h2>
<div class="flow-grid">
<div class="flow-card"><div class="flow-icon">🧾</div><strong>1. 商品情報を取得</strong><p>価格・容量・個数・送料条件を楽天の商品情報から確認。</p></div>
<div class="flow-arrow">→</div>
<div class="flow-card"><div class="flow-icon">⚖️</div><strong>2. 同じ単位にそろえる</strong><p>1食・1kg・1L・100gあたりへ換算して比較できる形に。</p></div>
<div class="flow-arrow">→</div>
<div class="flow-card"><div class="flow-icon">🏆</div><strong>3. 安い順で見る</strong><p>数量が曖昧な商品は外し、送料込みの商品を先にランキング。</p></div>
</div>
</section>"""


CSS = """*{box-sizing:border-box}
:root{--bg:#f7f4ec;--panel:#fffdf8;--ink:#17211a;--muted:#687068;--line:#e4e0d4;--brand:#246b49;--brand2:#173f31;--brand-soft:#e8f2e9;--warm:#fff0cf;--warm-ink:#825719;--shadow:0 18px 50px rgba(50,60,45,.10)}
html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 10% 0,#fff9e9 0,transparent 30%),var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.65}
a{color:inherit}.wrap{width:min(1120px,calc(100% - 28px));margin:auto}
header{position:relative;overflow:hidden;background:linear-gradient(135deg,#fffdf7 0%,#edf7ee 55%,#fff2d8 100%);border-bottom:1px solid var(--line);padding:42px 0 34px}
header:after{content:"";position:absolute;right:-90px;top:-120px;width:320px;height:320px;border-radius:50%;background:#ffffff70}
.hero-layout{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);gap:28px;align-items:center;position:relative;z-index:1}
.brand{font-size:12px;font-weight:950;letter-spacing:.12em;color:var(--brand);text-decoration:none}.eyebrow{display:inline-block;background:#fff;border:1px solid #dce8dd;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:900;color:var(--brand)}
h1{font-size:clamp(32px,6vw,58px);line-height:1.08;margin:12px 0 16px;letter-spacing:-.035em}h2{font-size:clamp(22px,4vw,30px);line-height:1.3;letter-spacing:-.02em}
.lead{font-size:clamp(15px,2.2vw,19px);max-width:720px}.lead,.sub,.note{color:var(--muted)}.note{font-size:12px}
.hero-tags{display:flex;gap:7px;flex-wrap:wrap;margin:18px 0 8px}.hero-tag{font-size:11px;font-weight:850;background:#fff;color:var(--brand);border:1px solid #dce8dd;border-radius:999px;padding:6px 10px}
.hero-art-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;transform:rotate(1.5deg)}.hero-art-item{min-height:150px;border-radius:28px;display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow);border:1px solid #ffffffbb}.hero-art-item.rice{background:#f3e8b9}.hero-art-item.pack-rice{background:#ffe0bf}.hero-art-item.carbonated-water{background:#d8f2fa}.hero-art-item.oatmeal{background:#ead6be}.food-art{display:block;width:min(100%,250px);height:auto}.food-art.compact{width:min(100%,180px)}
.nav{position:sticky;top:0;background:#fffdf8ed;border-bottom:1px solid var(--line);z-index:10;backdrop-filter:blur(12px)}.nav .wrap{display:flex;gap:8px;overflow:auto;padding:9px 14px}.nav a{white-space:nowrap;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:#fff;font-size:12px;font-weight:800}
.section-kicker{font-size:11px;letter-spacing:.12em;font-weight:950;color:var(--brand);text-transform:uppercase}.grid{display:grid;gap:16px;margin:26px 0}.card,.explain,.summary{background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:20px;text-decoration:none;box-shadow:0 8px 24px rgba(50,60,45,.04)}
.category-card{display:grid;grid-template-columns:155px 1fr;gap:18px;align-items:center;position:relative;overflow:hidden;transition:transform .16s ease,box-shadow .16s ease}.category-card:hover{transform:translateY(-4px);box-shadow:var(--shadow)}.category-card.rice{background:linear-gradient(135deg,#fffdf7,#f3e8b9)}.category-card.pack-rice{background:linear-gradient(135deg,#fffdf7,#ffe0bf)}.category-card.carbonated-water{background:linear-gradient(135deg,#fffdf7,#d8f2fa)}.category-card.oatmeal{background:linear-gradient(135deg,#fffdf7,#ead6be)}
.category-art{height:150px;display:flex;align-items:center;justify-content:center}.category-copy{min-width:0}.category-name{font-size:19px;font-weight:950}.category-price{font-size:28px;line-height:1.12;color:var(--brand2);font-weight:950;margin:8px 0 2px}.category-meta{font-size:12px;color:var(--muted);font-weight:750}.category-go{display:inline-flex;margin-top:10px;font-size:12px;font-weight:950;color:#fff;background:var(--brand);padding:8px 12px;border-radius:999px}
.section{margin:34px 0 52px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.toolbar select,.toolbar input{min-height:44px;border:1px solid var(--line);border-radius:12px;background:#fff;padding:0 12px;font-weight:750}.toolbar input{flex:1;min-width:220px}.toolbar input::placeholder{color:#8b918c;font-weight:600}
.summary{margin:22px 0 14px}.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.summary-item{background:#f5f8f2;border:1px solid #e2e9df;border-radius:16px;padding:14px}.summary-k{font-size:11px;color:var(--muted);font-weight:850}.summary-v{font-size:23px;font-weight:950;color:var(--brand);margin-top:3px}
.podium-section{background:linear-gradient(135deg,#173f31,#2b7754);color:#fff;border-radius:28px;padding:26px;box-shadow:var(--shadow)}.podium-section .sub{color:#dcebe2}.podium-section .section-kicker{color:#d9f1df}.podium-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.podium-card{background:#fff;color:var(--ink);border-radius:20px;padding:15px;display:flex;flex-direction:column;min-width:0}.podium-card.rank-1{transform:translateY(-5px);box-shadow:0 14px 32px rgba(0,0,0,.18)}.podium-head{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:950}.podium-medal{font-size:23px}.podium-media{height:115px;display:flex;align-items:center;justify-content:center;margin:8px 0}.podium-img{max-width:100%;max-height:110px;object-fit:contain}.podium-name{font-size:13px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.podium-unit{font-size:28px;color:var(--brand);font-weight:950;margin-top:10px}.podium-label,.podium-detail{font-size:11px;color:var(--muted)}.podium-detail{margin:6px 0 10px}.podium-cta{margin-top:auto}
.table{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:18px}table{border-collapse:collapse;width:100%;min-width:800px}th,td{padding:11px;border-bottom:1px solid #ebe9e0;text-align:left;font-size:12px;vertical-align:top}th{background:#f3f5ef;font-size:11px;color:#56615a}
.product-name{display:block;font-size:13px;line-height:1.45}.shop{color:var(--muted);margin:4px 0 6px}.product-img{width:72px;height:72px;object-fit:contain;border-radius:12px;background:#fff}.rank{font-size:15px;font-weight:950}.rank.top{display:inline-flex;width:30px;height:30px;align-items:center;justify-content:center;border-radius:50%;background:var(--brand);color:#fff}.unit{font-size:20px;font-weight:950;color:var(--brand);white-space:nowrap}.unit-label{font-size:10px;color:var(--muted);font-weight:750}.secondary-unit{font-size:11px;color:#536058;margin-top:3px}
.tag{display:inline-block;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:850;margin:2px 2px 0 0}.ok{background:var(--brand-soft);color:var(--brand)}.warn{background:var(--warm);color:var(--warm-ink)}.cta{display:inline-flex;justify-content:center;align-items:center;min-height:40px;padding:0 11px;border-radius:11px;background:var(--brand);color:#fff;text-decoration:none;font-weight:900;white-space:nowrap}
.guide-list{margin:10px 0 0;padding-left:20px}.guide-list li{margin:7px 0}.fine{font-size:11px;color:var(--muted)}.other-categories{display:flex;gap:8px;flex-wrap:wrap}.other-categories a{border:1px solid var(--line);background:#fff;border-radius:999px;padding:8px 11px;text-decoration:none;font-size:12px;font-weight:850}.empty-filter{display:none;background:#fff;border:1px dashed var(--line);border-radius:14px;padding:18px;color:var(--muted);text-align:center}
.flow-section{padding:28px;border-radius:28px;background:#fffdf8;border:1px solid var(--line);box-shadow:var(--shadow)}.flow-grid{display:grid;grid-template-columns:1fr 42px 1fr 42px 1fr;align-items:stretch;gap:8px;margin-top:18px}.flow-card{border-radius:18px;background:#f7f6ef;padding:18px}.flow-card strong{display:block;font-size:15px}.flow-card p{font-size:12px;color:var(--muted);margin-bottom:0}.flow-icon{font-size:30px;margin-bottom:8px}.flow-arrow{display:flex;align-items:center;justify-content:center;color:var(--brand);font-size:26px;font-weight:950}
.category-hero-art{background:#fff;border:1px solid #ffffffaa;border-radius:26px;min-height:245px;display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow)}
.finder{background:linear-gradient(135deg,#fffdf8,#f2f7ec);border:1px solid var(--line);border-radius:30px;padding:28px;box-shadow:var(--shadow)}.finder-step{display:grid;grid-template-columns:38px 1fr;gap:12px;align-items:start;margin-top:20px}.finder-number{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--brand);color:#fff;font-weight:950}.finder-options{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}.finder-options button{border:1px solid var(--line);background:#fff;border-radius:16px;padding:10px 14px;font-weight:850;cursor:pointer;color:var(--ink);transition:.15s}.finder-options button:hover,.finder-options button.selected{border-color:var(--brand);box-shadow:0 8px 22px rgba(36,107,73,.12);transform:translateY(-1px)}.finder-category{display:flex;align-items:center;gap:8px}.finder-art{width:52px;height:42px;display:inline-flex;align-items:center;justify-content:center}.finder-art .food-art{max-width:58px;max-height:46px}.finder-step-muted{opacity:.52;transition:.15s}.finder-step-muted.active{opacity:1}.finder-result{margin-top:22px;background:var(--brand2);color:#fff;border-radius:20px;padding:16px;display:flex;align-items:center;justify-content:space-between;gap:18px}.finder-result[hidden]{display:none}.finder-result-label{display:block;font-size:10px;font-weight:900;color:#cde4d7;letter-spacing:.08em}.finder-result strong{display:block;font-size:18px;margin-top:2px}.finder-result p{margin:3px 0 0;color:#dcebe2;font-size:12px}.finder-go{background:#fff;color:var(--brand2);border-radius:12px;padding:11px 14px;text-decoration:none;font-weight:950;white-space:nowrap}.best{background:#ffe7a6;color:#725000}.top-badge{background:#e9edf8;color:#43527a}.lifestyle{background:#eee9ff;color:#58488d}.product-badges{margin-top:4px}.podium-badges{min-height:24px;margin-top:4px}.podium-diff{display:inline-block;align-self:flex-start;margin-top:7px;background:#eef5ee;color:var(--brand);border-radius:999px;padding:3px 7px;font-size:10px;font-weight:900}

.hero-visual{position:relative;min-height:350px;display:flex;align-items:center;justify-content:center}.hero-visual .guide-mascot{width:min(90%,330px);filter:drop-shadow(0 20px 25px rgba(23,63,49,.13))}.guide-mascot.compact{width:95px;height:auto}.mascot-bubble{position:absolute;right:8px;top:12px;background:#fff;border:1px solid #dce8dd;border-radius:20px 20px 20px 5px;padding:12px 15px;font-size:12px;line-height:1.4;box-shadow:0 12px 28px rgba(40,60,45,.08);z-index:2}.hero-food-chip{position:absolute;background:#fff;border:1px solid #e2e6dd;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:900;box-shadow:0 10px 24px rgba(50,60,45,.08)}.chip-rice{left:4%;top:18%}.chip-water{right:2%;bottom:26%}.chip-pack{left:0;bottom:24%}.chip-oats{right:8%;top:31%}
.finder-intro{display:flex;align-items:center;justify-content:space-between;gap:18px}.finder-guide{display:flex;align-items:center;gap:4px;font-size:11px;font-weight:900;color:var(--brand)}.finder-stage{margin-top:18px}.finder-stage[hidden],.finder-picks[hidden]{display:none}.finder-question{display:flex;align-items:center;gap:10px}.finder-question>span{display:inline-flex;width:34px;height:34px;border-radius:50%;align-items:center;justify-content:center;background:var(--brand2);color:#fff;font-size:11px;font-weight:950}.finder-question>strong{font-size:20px}.finder-category-options button{min-width:180px}.finder-purpose-options button{display:flex;align-items:center;gap:9px;font-size:20px;text-align:left}.finder-purpose-options button span{display:flex;flex-direction:column}.finder-purpose-options button strong{font-size:14px}.finder-purpose-options button small{font-size:10px;color:var(--muted);font-weight:700}.finder-back{border:0;background:transparent;color:var(--brand);font-weight:850;padding:0;margin-bottom:12px;cursor:pointer}.finder-picks{margin-top:8px}.finder-picks-head span{display:block;font-size:10px;font-weight:950;color:var(--brand);letter-spacing:.08em}.finder-picks-head strong{font-size:20px}.finder-products{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}.finder-product{display:grid;grid-template-rows:110px 1fr;background:#fff;border:1px solid var(--line);border-radius:18px;overflow:hidden}.finder-product-media{display:flex;align-items:center;justify-content:center;padding:8px;background:#fafbf7}.finder-product-media img{max-width:100%;max-height:100px;object-fit:contain}.finder-product-copy{position:relative;padding:13px;display:flex;flex-direction:column}.finder-product-copy>strong{font-size:12px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.finder-product-rank{position:absolute;right:10px;top:-18px;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--brand);color:#fff;font-weight:950}.finder-product-price{font-size:22px;font-weight:950;color:var(--brand);margin-top:10px}.finder-product-price small{font-size:10px;color:var(--muted)}.finder-product-meta{font-size:10px;color:var(--muted);margin:4px 0 7px}.finder-why{font-size:10px;color:#536058;background:#f3f7f2;border-radius:9px;padding:6px 7px;margin-bottom:9px}.finder-why span{display:inline-block;font-weight:950;color:var(--brand);margin-right:5px}.finder-product-copy .cta{margin-top:auto}.finder-all{display:inline-flex;margin-top:12px;color:var(--brand);font-weight:900;text-decoration:none}
.more-products{margin:28px 0 40px}.more-products>summary{list-style:none;cursor:pointer;background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 18px;font-weight:950;display:flex;align-items:center;justify-content:space-between;box-shadow:0 5px 16px rgba(50,60,45,.04)}.more-products>summary::-webkit-details-marker{display:none}.more-products[open]>summary span{transform:rotate(45deg)}.more-products .comparison-inner{margin-top:12px}.comparison-inner>h2{margin-top:0}.after-top3{margin-top:-10px}.guide-with-mascot{display:grid;grid-template-columns:1fr 120px;gap:20px;align-items:center}.guide-mini{display:flex;justify-content:center}
.intent-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.intent-card{display:flex;flex-direction:column;gap:5px;background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px;text-decoration:none;transition:.15s}.intent-card:hover{transform:translateY(-2px);box-shadow:var(--shadow)}.intent-card span{font-weight:950}.intent-card small{color:var(--muted);line-height:1.45}.intent-card b{color:var(--brand);font-size:12px;margin-top:4px}.insight-section{background:linear-gradient(135deg,#fffdf8,#eef6ee);border:1px solid var(--line);border-radius:24px;padding:24px}.insight-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}.insight-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px}.insight-card span{display:block;font-size:11px;font-weight:850;color:var(--muted)}.insight-card strong{display:block;font-size:25px;color:var(--brand);line-height:1.2;margin-top:5px}.insight-card small{color:var(--muted)}
.product-actions{display:flex;gap:6px;flex-wrap:wrap;margin:7px 0}.utility-btn{border:1px solid #d7ded7;background:#fff;color:#405048;border-radius:999px;padding:6px 9px;font-size:10px;font-weight:850;cursor:pointer}.utility-btn.active{background:var(--brand-soft);border-color:#9fc4aa;color:var(--brand)}.podium-card .product-actions{margin-top:9px}.podium-card .utility-btn{flex:1}
.saved-fab{position:fixed;right:16px;bottom:18px;z-index:24;border:0;background:#fff;color:var(--brand2);box-shadow:0 10px 30px rgba(20,40,28,.18);border-radius:999px;padding:11px 15px;font-weight:950;cursor:pointer}.saved-fab span{display:inline-flex;min-width:20px;height:20px;align-items:center;justify-content:center;background:var(--brand);color:#fff;border-radius:50%;font-size:10px;margin-left:4px}
.compare-bar{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:23;width:min(760px,calc(100% - 150px));background:var(--brand2);color:#fff;border-radius:18px;padding:10px 12px;display:flex;align-items:center;gap:10px;box-shadow:0 16px 36px rgba(18,39,29,.25)}.compare-bar[hidden]{display:none}.compare-bar>div:first-child{min-width:95px}.compare-bar strong{display:block;font-size:11px}.compare-bar [data-compare-summary]{font-size:10px;color:#cfe1d5}.compare-bar-items{display:flex;gap:5px;overflow:hidden;flex:1}.compare-chip{max-width:150px;background:#ffffff18;border-radius:999px;padding:5px 8px;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compare-open,.compare-clear{border:0;border-radius:10px;padding:8px 10px;font-weight:900;cursor:pointer}.compare-open{background:#fff;color:var(--brand2)}.compare-clear{background:transparent;color:#d7e5dc}
.utility-modal{position:fixed;inset:0;background:#10211899;z-index:40;padding:20px;display:flex;align-items:flex-end;justify-content:center}.utility-modal[hidden]{display:none}.utility-sheet{position:relative;width:min(620px,100%);max-height:82vh;overflow:auto;background:#fffdf8;border-radius:24px 24px 12px 12px;padding:24px;box-shadow:0 24px 60px rgba(0,0,0,.25)}.utility-sheet-wide{width:min(920px,100%)}.utility-close{position:absolute;right:16px;top:14px;border:0;background:#eef3ed;width:34px;height:34px;border-radius:50%;font-size:22px;cursor:pointer}.saved-item{display:grid;grid-template-columns:58px 1fr auto;gap:10px;align-items:center;border-top:1px solid var(--line);padding:10px 0}.saved-item img{width:54px;height:54px;object-fit:contain}.saved-item strong{font-size:12px;line-height:1.4}.saved-item small{display:block;color:var(--muted)}.saved-item button{border:0;background:transparent;color:#8a4b45;cursor:pointer}.site-toast{position:fixed;left:50%;bottom:95px;transform:translateX(-50%);z-index:60;background:#17211a;color:#fff;border-radius:999px;padding:9px 14px;font-size:11px;font-weight:850;box-shadow:0 10px 28px rgba(0,0,0,.22)}.site-toast[hidden]{display:none}.utility-empty{padding:24px 0;color:var(--muted);text-align:center}.compare-table{width:100%;overflow:auto}.compare-table table{min-width:620px}.compare-table th:first-child{position:sticky;left:0;background:#f3f5ef;z-index:1}.compare-table td:first-child{font-weight:900;background:#fffdf8}.compare-table a{color:var(--brand);font-weight:900}
.faq-section{background:#fffdf8;border:1px solid var(--line);border-radius:24px;padding:24px}.faq-item{border-top:1px solid var(--line);padding:12px 0}.faq-item:first-of-type{border-top:0}.faq-item summary{cursor:pointer;font-weight:900}.faq-item p{color:var(--muted);margin:8px 0 0}
footer{background:#fff;border-top:1px solid var(--line);padding:30px 0 42px;color:var(--muted);font-size:11px}
@media(min-width:760px){.grid{grid-template-columns:1fr 1fr}}
@media(max-width:759px){
 .wrap{width:min(100% - 20px,1120px)}header{padding:25px 0 20px}.hero-layout{grid-template-columns:1fr;gap:18px}.hero-art-grid{grid-template-columns:1fr 1fr;gap:8px}.hero-art-item{min-height:105px;border-radius:20px}.hero-art-item .food-art{max-height:100px}.category-hero-art{min-height:180px}.category-hero-art .food-art{max-height:175px}
 .grid{grid-template-columns:1fr}.category-card{grid-template-columns:105px 1fr;padding:14px}.category-art{height:110px}.category-art .food-art{max-height:105px}.category-price{font-size:24px}
 .podium-grid{grid-template-columns:1fr}.podium-card.rank-1{transform:none}.summary-grid{grid-template-columns:1fr 1fr}.summary-item:first-child{grid-column:1/-1}.flow-grid{grid-template-columns:1fr}.flow-arrow{transform:rotate(90deg);height:24px}.finder{padding:20px 15px}.finder-options{display:grid;grid-template-columns:1fr 1fr}.finder-options button{width:100%;text-align:left}.finder-result{align-items:stretch;flex-direction:column}.finder-go{text-align:center}
 .insight-grid{grid-template-columns:1fr}.compare-bar{left:10px;right:10px;bottom:72px;transform:none;width:auto;flex-wrap:wrap}.compare-bar-items{order:3;width:100%}.saved-fab{right:10px;bottom:14px}.utility-modal{padding:8px}.utility-sheet{border-radius:22px 22px 8px 8px;padding:20px 15px}.intent-grid{grid-template-columns:1fr}.hero-visual{min-height:245px}.hero-visual .guide-mascot{width:240px}.mascot-bubble{right:0;top:0}.hero-food-chip{font-size:10px;padding:5px 8px}.finder-intro{align-items:flex-start}.finder-guide span{display:none}.finder-products{grid-template-columns:1fr}.finder-product{grid-template-columns:92px 1fr;grid-template-rows:auto}.finder-product-media{min-height:120px}.finder-product-copy>strong{-webkit-line-clamp:2}.guide-with-mascot{grid-template-columns:1fr 80px;gap:10px}.guide-mini .guide-mascot{width:75px} .table{overflow:visible;background:transparent;border:0}table,tbody{display:block;width:100%;min-width:0}thead{display:none}tr{display:grid;grid-template-columns:76px 1fr;gap:0 12px;background:#fff;border:1px solid var(--line);border-radius:16px;margin:10px 0;padding:13px;box-shadow:0 2px 8px #13291b08}
 td{display:block;border:0;padding:3px 0;font-size:12px;min-width:0}td[data-cell="rank"]{grid-column:1/-1;padding-bottom:5px}td[data-cell="image"]{grid-column:1;grid-row:2 / span 4}td[data-cell="product"],td[data-cell="quantity"],td[data-cell="price"],td[data-cell="unit"],td[data-cell="cta"]{grid-column:2}
 td[data-cell="product"]{padding-top:0}.product-img{width:72px;height:72px}.product-name{font-size:14px}.unit{font-size:23px;margin-top:3px}td[data-cell="quantity"]::before{content:"内容量  ";font-weight:800;color:var(--muted)}td[data-cell="price"]::before{content:"商品価格  ";font-weight:800;color:var(--muted)}td[data-cell="cta"]{margin-top:8px}.cta{width:100%;min-height:46px}.toolbar select,.toolbar input{flex:1;min-width:0;width:100%}.section{margin:26px 0 38px}
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
  const x={affiliate:'rakuten',conversion_source:'category',category_id:a.dataset.category,product_id:a.dataset.productId,product_name:a.dataset.productName,rank:a.dataset.rank,comparison_metric:a.dataset.metric,unit_price:Number(a.dataset.unitPrice||0),shipping_status:a.dataset.shipping,click_position:a.dataset.position||'comparison_table',link_url:a.href};
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
const finder=document.querySelector('[data-finder]');
if(finder){
  let category='';
  const categoryStage=finder.querySelector('[data-finder-category-stage]');
  const purposeStage=finder.querySelector('[data-finder-purpose-stage]');
  const resultStage=finder.querySelector('[data-finder-result-stage]');
  const qTitle=finder.querySelector('[data-finder-question-title]');
  const show=el=>{if(el)el.hidden=false};
  const hide=el=>{if(el)el.hidden=true};
  const reset=()=>{
    category='';
    show(categoryStage);hide(purposeStage);hide(resultStage);
    finder.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));
    finder.querySelectorAll('[data-finder-picks]').forEach(x=>x.hidden=true)
  };
  finder.querySelectorAll('[data-finder-category]').forEach(btn=>btn.addEventListener('click',()=>{
    category=btn.dataset.finderCategory;
    finder.querySelectorAll('[data-finder-category]').forEach(x=>x.classList.toggle('selected',x===btn));
    qTitle.textContent=btn.dataset.finderName+'は、どう買いたい？';
    hide(categoryStage);show(purposeStage);hide(resultStage);
    send('quick_finder_category',{category_id:category})
  }));
  finder.querySelectorAll('[data-finder-purpose]').forEach(btn=>btn.addEventListener('click',()=>{
    if(!category)return;
    const purpose=btn.dataset.finderPurpose;
    finder.querySelectorAll('[data-finder-picks]').forEach(panel=>panel.hidden=panel.dataset.finderPicks!==category+':'+purpose);
    hide(categoryStage);hide(purposeStage);show(resultStage);
    send('quick_finder_complete',{category_id:category,finder_purpose:purpose})
  }));
  finder.querySelector('[data-finder-back]')?.addEventListener('click',reset);
  finder.querySelector('[data-finder-reset]')?.addEventListener('click',reset);
}
const pick=new URLSearchParams(location.search).get('pick');
if(pick&&document.querySelector('[data-comparison]')){
  const root=document.querySelector('[data-comparison]');
  const filter=root.querySelector('[data-filter]');
  const sort=root.querySelector('[data-sort]');
  if(filter&&(pick==='small'||pick==='large'))filter.value=pick;
  if(filter&&pick==='storage')filter.value='small';
  if(sort&&(pick==='budget'||pick==='storage')){sort.value='price';sort.dispatchEvent(new Event('change'))}
  const details=root.closest('details');if(details)details.open=true;
  applyFilters(root);
  send('quick_finder_landing',{category_id:filter?.dataset.category||'',finder_purpose:pick})
}
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


def rows_html(items: list[dict], category: dict, start_rank: int = 1) -> str:
    rows = []
    for rank, item in enumerate(items, start=start_rank):
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
        recommendation = item_badges(item, category, rank)
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
<td data-cell="product"><strong class="product-name">{html.escape(item['name'])}</strong><div class="shop">{html.escape(item['shop'])}</div><div class="product-badges">{recommendation} {shipping} {promo}</div></td>
<td data-cell="quantity">{html.escape(quantity_text(item, category['id']))}</td>
<td data-cell="price">¥{item['price']:,}</td>
<td data-cell="unit"><div class="unit">{yen(primary)}</div><div class="unit-label">{html.escape(category['primary_label'])}</div>{secondary}</td>
<td data-cell="cta">{product_action_buttons(item, category, primary)}<a class="cta" href="{html.escape(item['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{primary_metric}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}">楽天で価格を見る →</a></td>
</tr>"""
        )
    return "".join(rows)


def comparison_table(
    items: list[dict],
    category: dict,
    title: str,
    note: str,
    start_rank: int = 1,
    collapsed: bool = False,
) -> str:
    if not items:
        return ""

    options = [
        f'<option value="{category["primary"]}">{category["primary_label"]}が安い順</option>',
        '<option value="price">商品価格が安い順</option>',
    ]
    if category["secondary"]:
        options.insert(
            1,
            f'<option value="{category["secondary"]}">{category["secondary_label"]}が安い順</option>',
        )

    content = f"""<section class="comparison-inner" data-comparison>
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
<tbody>{rows_html(items, category, start_rank)}</tbody>
</table></div>
</section>"""
    if not collapsed:
        return content
    return f"""<details class="more-products" data-more-products>
<summary>{html.escape(title)} <span>＋</span></summary>
{content}
</details>"""

def faq_json_ld(faqs: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in faqs
        ],
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'


def faq_html(faqs: list[tuple[str, str]]) -> str:
    items = "".join(
        f"""<details class="faq-item"><summary>{html.escape(question)}</summary><p>{html.escape(answer)}</p></details>"""
        for question, answer in faqs
    )
    return f"""<section class="section faq-section"><div class="section-kicker">FAQ</div><h2>よくある質問</h2>{items}</section>"""


def category_faq(category: dict) -> list[tuple[str, str]]:
    return [
        (
            f"{category['name']}は何を基準に並べていますか？",
            f"送料込み確認済みの商品を、主に{category['primary_label']}が安い順で並べています。",
        ),
        (
            "クーポンやポイントは単価に含めていますか？",
            "通常価格を公平に比べるため、クーポンやポイントは自動的に単価へ差し引いていません。",
        ),
        (
            "数量が選べる商品はランキングに入りますか？",
            "購入する容量や個数を商品情報から一意に確定できない場合は、誤比較を防ぐためランキングから除外します。",
        ),
    ]


def guide_filter_items(spec: dict, items: list[dict], category: dict) -> list[dict]:
    mode = spec["mode"]
    if mode == "large":
        picked = [x for x in items if bucket(x, category["id"]) == "large"]
    elif mode == "pack_200":
        picked = [x for x in items if 180 <= float(x["quantity"].get("unit_weight_g") or 0) <= 210]
    elif mode == "rice_5kg":
        picked = [x for x in items if 4500 <= float(x["quantity"].get("total_weight_g") or 0) <= 5500]
    elif mode == "rice_10kg":
        picked = [x for x in items if 9000 <= float(x["quantity"].get("total_weight_g") or 0) <= 11000]
    elif mode == "count_24":
        picked = [x for x in items if int(x["quantity"].get("count") or 0) == 24]
    elif mode == "count_48":
        picked = [x for x in items if int(x["quantity"].get("count") or 0) == 48]
    elif mode == "oats_1kg":
        picked = [x for x in items if 900 <= float(x["quantity"].get("total_weight_g") or 0) <= 1100]
    else:
        picked = list(items)
    return picked


def guide_faq(spec: dict, category: dict) -> list[tuple[str, str]]:
    return [
        (
            f"{spec['title']}では何を比べていますか？",
            f"楽天から取得した商品情報をもとに、数量を確定できる商品だけを{category['primary_label']}へ換算して比較しています。",
        ),
        (
            "送料はランキングにどう反映していますか？",
            "主ランキングは楽天APIで送料込みと確認できる商品を対象にしています。地域別追加送料などは販売ページで最終確認してください。",
        ),
        (
            "一番上の商品が必ず自分に最適ですか？",
            "単価だけでなく、保管場所、支払総額、内容量、ブランドなども確認して選ぶのがおすすめです。",
        ),
    ]


def guide_page(spec: dict, category: dict, items: list[dict], updated: datetime) -> str:
    picked = guide_filter_items(spec, items, category)
    faqs = guide_faq(spec, category)
    canonical = f"{SITE_URL}guides/{spec['slug']}/"
    head = page_head(
        f"{spec['title']}｜食品コスパ比較",
        spec["intro"],
        canonical,
        faq_json_ld(faqs)
        + breadcrumb_json_ld([
            ("食品コスパ比較", SITE_URL),
            (category["name"], f"{SITE_URL}categories/{category['id']}/"),
            (spec["title"], canonical),
        ])
        + item_list_json_ld(picked, category),
    )
    cards = top3_html(picked, category) if picked else """<section class="section explain">
<h2>現在、条件に一致する掲載候補はありません</h2>
<p>別サイズの商品で穴埋めせず、条件に一致する商品を確認できたときだけ掲載します。</p>
</section>"""
    more = comparison_table(
        picked[3:],
        category,
        f"ほかの候補を見る（{max(0, len(picked)-3)}件）",
        "価格や容量条件を確認しながら比較できます。",
        start_rank=4,
        collapsed=True,
    ) if len(picked) > 3 else ""
    return head + f"""<header><div class="wrap hero-layout">
<div><a class="brand" href="../../">食品コスパ比較</a>
<div class="eyebrow">{category['emoji']} 検索テーマ別比較</div>
<h1>{html.escape(spec['h1'])}</h1>
<p class="lead">{html.escape(spec['intro'])}</p>
<div class="hero-tags"><span class="hero-tag">送料込みを優先</span><span class="hero-tag">実データ連動</span><span class="hero-tag">数量曖昧は除外</span></div>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST</p></div>
<div class="category-hero-art {category['id']}">{category_illustration(category['id'])}</div>
</div></header>
<main class="wrap">
<section class="section explain"><h2>このページの見方</h2>
<p>{html.escape(spec['intro'])}</p>
<p class="fine">商品名・容量・セット数を安全に読み取れない候補は除外し、クーポンやポイントは通常単価へ自動反映しません。</p>
</section>
{cards}
{more}
{faq_html(faqs)}
<section class="section explain"><h2>もっと広く比較する</h2><p><a class="finder-go" href="../../categories/{category['id']}/">{category['emoji']} {html.escape(category['name'])}の全ランキングを見る →</a></p></section>
{utility_panels_html()}
</main><script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。価格は取得時点の参考情報です。</div></footer>
</body></html>"""



def page_head(title: str, description: str, canonical: str, extra_head: str = "") -> str:
    return f"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description, quote=True)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<style>{CSS}</style>
{ga_head()}
{extra_head}
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
    return f"""<section class="section explain guide-with-mascot">
<div><h2>{category['emoji']} {html.escape(category['name'])}を比べるコツ</h2>
<ul class="guide-list">{points}</ul></div>
<div class="guide-mini">{guide_mascot(True)}</div>
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
    faqs = category_faq(category)
    parts = [
        page_head(
            f"{category['name']}のコスパ比較｜{category['primary_label']}・送料込み",
            f"{category['name']}を{category['primary_label']}へ換算し、容量・セット数・送料条件をそろえて比較します。",
            f"{SITE_URL}categories/{category['id']}/",
            faq_json_ld(faqs)
            + breadcrumb_json_ld([
                ("食品コスパ比較", SITE_URL),
                (category["name"], f"{SITE_URL}categories/{category['id']}/"),
            ])
            + item_list_json_ld(included, category),
        )
    ]
    parts.append(
        f"""<header><div class="wrap hero-layout">
<div>
<a class="brand" href="../../">食品コスパ比較</a>
<div class="eyebrow">{category["emoji"]} {category["name"]}</div>
<h1>{category["name"]}を<br>{category["primary_label"]}で比較。</h1>
<p class="lead">{category["intro"]}</p>
<div class="hero-tags"><span class="hero-tag">送料込みを優先</span><span class="hero-tag">数量曖昧は除外</span><span class="hero-tag">クーポン未反映</span></div>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST。最新価格は販売ページで確認してください。</p>
</div>
<div class="category-hero-art {category['id']}">{category_illustration(category["id"])}</div>
</div></header>
<nav class="nav"><div class="wrap">
<a href="#included">送料込み比較</a>
<a href="#other">送料別参考</a>
<a href="../../">トップ</a>
</div></nav>
<main class="wrap">"""
    )
    parts.append(category_summary(category, included, other))
    parts.append(category_insights_html(category, included))
    parts.append(top3_html(included, category))
    remaining = included[3:]
    if remaining:
        parts.append(
            '<div id="included" class="after-top3">'
            + comparison_table(
                remaining,
                category,
                f"4位以下を見る（{len(remaining)}件）",
                "必要なときだけ開いて、検索・並び替え・容量条件で絞り込めます。",
                start_rank=4,
                collapsed=True,
            )
            + "</div>"
        )
    if other:
        parts.append(
            '<div id="other">'
            + comparison_table(
                other,
                category,
                f"送料別の参考商品を見る（{len(other)}件）",
                "単価は商品価格だけの参考値です。送料額は推測せず、送料込みランキングと混ぜません。",
                collapsed=True,
            )
            + "</div>"
        )
    parts.append(guide_html(category))
    parts.append(faq_html(faqs))
    parts.append(other_categories_html(category["id"]))
    parts.append(
        """<section class="section explain">
<h2>このランキングのルール</h2>
<p>数量を安全に読み取れる商品だけを掲載し、定期購入・初回限定などは通常価格ランキングから除外します。クーポン・ポイントは通常単価へ差し引きません。</p>
<p class="fine">送料込みは楽天APIの送料フラグを基準にし、地域別の追加送料などは販売ページで最終確認してください。</p>
</section>
{utility_panels_html()}
</main>"""
    )
    parts.append(
        f"""<script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。価格は取得時点の参考情報です。</div></footer>
</body></html>"""
    )
    return "".join(parts)


def guide_links_html() -> str:
    links = "".join(
        f"""<a class="intent-card" href="guides/{spec['slug']}/">
<span>{html.escape(spec['title'])}</span><small>{html.escape(spec['intro'])}</small><b>比較を見る →</b>
</a>"""
        for spec in GUIDE_SPECS
    )
    return f"""<section class="section intent-section">
<div class="section-kicker">POPULAR SEARCHES</div>
<h2>よく比べられる条件から探す。</h2>
<div class="intent-grid">{links}</div>
</section>"""



def home_page(results: dict, updated: datetime) -> str:
    parts = [
        page_head(
            "食品コスパ比較｜容量・数量・送料をそろえて単価比較",
            "米、パックご飯、炭酸水、オートミールを1kg・1L・1食・100gあたりへ換算し、送料条件を分けて比較します。",
            SITE_URL,
        )
    ]
    parts.append(
        f"""<header><div class="wrap hero-layout">
<div>
<span class="brand">FOOD COST</span>
<div class="eyebrow">かしこく買うための食品比較</div>
<h1>値札より、<br>「ほんとの単価」を見よう。</h1>
<p class="lead">容量・本数・食数・セット数を同じものさしにそろえて比較。家計にうれしい商品を、数字だけでなく見た目でも探しやすくしました。</p>
<div class="hero-tags"><span class="hero-tag">送料込みを優先</span><span class="hero-tag">数量曖昧は除外</span><span class="hero-tag">楽天価格を再取得</span></div>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST</p>
</div>
{hero_visual()}
</div></header>
<main class="wrap">
{choice_finder_html(results)}
<section class="section">
<div class="section-kicker">CHOOSE A CATEGORY</div>
<h2>まず、比べたい食品を選ぶ。</h2>
<section class="grid">"""
    )
    for category in CATEGORIES:
        included, _ = results[category["id"]]
        best = included[0]["unit_prices"][category["primary"]] if included else None
        message = (
            f"取得商品では {category['primary_label']} {yen(best)}〜"
            if best is not None else "比較データを準備中"
        )
        parts.append(
            f"""<a class="card category-card {category['id']}" href="categories/{category['id']}/">
<div class="category-art">{category_illustration(category["id"], True)}</div>
<div class="category-copy">
<div class="category-name">{category['emoji']} {category['name']}</div>
<div class="category-price">{html.escape(message.replace('取得商品では ', ''))}</div>
<div class="category-meta">送料込み {len(included)}件を比較中</div>
<p>{html.escape(category['intro'])}</p>
<span class="category-go">ランキングを見る →</span>
</div>
</a>"""
        )
    parts.append(
        """</section></section>"""
    )
    parts.append(guide_links_html())
    parts.append(comparison_flow_html())
    parts.append(
        """<section class="section explain">
<h2>このサイトの比較ルール</h2>
<p>送料込み確認済みを主ランキングにし、送料別は別枠。容量・数量が曖昧な商品は無理に計算しません。定期便・初回限定価格も通常ランキングへ混ぜません。</p>
<ul class="guide-list">
<li>容量やセット数を同じ単位に換算して比較</li>
<li>クーポンやポイントは通常単価へ勝手に差し引かない</li>
<li>販売数量を一意に確定できない商品はランキングから除外</li>
</ul>
</section>
{utility_panels_html()}
</main>"""
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

    category_by_id = {category["id"]: category for category in CATEGORIES}
    for spec in GUIDE_SPECS:
        category = category_by_id[spec["category_id"]]
        included, _ = results[category["id"]]
        target = OUT / "guides" / spec["slug"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(
            guide_page(spec, category, included, updated),
            encoding="utf-8",
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
    ] + [
        f"{SITE_URL}guides/{spec['slug']}/"
        for spec in GUIDE_SPECS
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
