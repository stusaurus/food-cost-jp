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
from price_history import apply_price_history, load_price_history, save_price_history

SITE_ID = "food_cost_jp"
SITE_URL = "https://stusaurus.github.io/food-cost-jp/"
API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
OUT = Path("site")
HISTORY_SOURCE = Path("data/price-history.json")
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

AUTO_GUIDE_RULES = [
    {"slug":"pack-rice-24-servings-cost","category_id":"pack-rice","title":"パックご飯24食のコスパ比較","h1":"パックご飯24食を1食あたりで比較","intro":"24食セットのパックご飯が3商品以上あるときだけ自動公開し、1食あたりの単価で比較します。","mode":"pack_count_24","auto":True},
    {"slug":"pack-rice-40plus-cost","category_id":"pack-rice","title":"パックご飯40食以上のコスパ比較","h1":"パックご飯40食以上の大箱を比較","intro":"40食以上の大箱候補が3商品以上あるときだけ自動公開し、単価と支払総額を比べます。","mode":"pack_count_40plus","auto":True},
    {"slug":"carbonated-water-500ml-24-cost","category_id":"carbonated-water","title":"炭酸水500ml前後24本のコスパ比較","h1":"炭酸水500ml前後×24本を比較","intro":"450〜600ml・24本の候補が3商品以上あるときだけ自動公開し、1L・1本あたりで比較します。","mode":"water_500_24","auto":True},
    {"slug":"carbonated-water-500ml-48-cost","category_id":"carbonated-water","title":"炭酸水500ml前後48本のコスパ比較","h1":"炭酸水500ml前後×48本を比較","intro":"450〜600ml・48本の候補が3商品以上あるときだけ自動公開し、まとめ買い単価を比べます。","mode":"water_500_48","auto":True},
    {"slug":"carbonated-water-1l-cost","category_id":"carbonated-water","title":"炭酸水1L前後のコスパ比較","h1":"炭酸水1L前後を1Lあたりで比較","intro":"900〜1100mlの商品が3商品以上あるときだけ自動公開し、1Lあたりの単価で比較します。","mode":"water_1l","auto":True},
    {"slug":"rice-musenmai-cost","category_id":"rice","title":"無洗米のコスパ比較","h1":"無洗米を1kgあたりで比較","intro":"商品名から無洗米と確認できる候補が3商品以上あるときだけ自動公開します。","mode":"rice_musenmai","auto":True},
    {"slug":"oatmeal-rolled-cost","category_id":"oatmeal","title":"ロールドオーツのコスパ比較","h1":"ロールドオーツを100gあたりで比較","intro":"商品名からロールドオーツと確認できる候補が3商品以上あるときだけ自動公開します。","mode":"oats_rolled","auto":True},
    {"slug":"oatmeal-quick-cost","category_id":"oatmeal","title":"クイックオーツのコスパ比較","h1":"クイックオーツを100gあたりで比較","intro":"商品名からクイックオーツと確認できる候補が3商品以上あるときだけ自動公開します。","mode":"oats_quick","auto":True},
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
    cls = "food-art compact" if compact else "food-art"
    return f'<img class="{cls}" src="{SITE_URL}assets/marche-{category_id}.webp" width="768" height="512" alt="" loading="lazy">'


def hero_illustrations() -> str:
    return hero_visual()


def guide_mascot(compact: bool = False) -> str:
    cls = "guide-mascot compact" if compact else "guide-mascot"
    return f'<img class="{cls}" src="{SITE_URL}assets/marche-rice.webp" width="768" height="512" alt="" loading="lazy">'


def hero_visual() -> str:
    return f'<div class="hero-visual"><img class="hero-scene" src="{SITE_URL}assets/marche-hero.webp" width="1440" height="960" alt="籐かごと米袋、炭酸水、オートミールが並ぶマルシェの店先" fetchpriority="high"><span class="hero-caption">A little market, a better everyday.</span></div>'


BRAND_HINTS = [
    "サトウのごはん", "サトウ食品", "アイリスオーヤマ", "アイリスフーズ",
    "テーブルマーク", "越後製菓", "ウーケ", "ウィルキンソン",
    "サントリー", "アサヒ", "伊藤園", "友桝飲料", "VOX", "ZAO SODA",
    "クエーカー", "日本食品製造", "日食", "ケロッグ",
]


def product_brand(name: str) -> str:
    text = str(name or "")
    matches = [brand for brand in BRAND_HINTS if brand.lower() in text.lower()]
    return max(matches, key=len) if matches else ""


def compact_product_name(name: str) -> str:
    text = re.sub(r"[【】\[\]〈〉《》]+", " ", str(name or ""))
    brand = product_brand(text)
    if brand:
        text = re.sub(re.escape(brand), " ", text, count=1, flags=re.I)
    text = re.sub(r"\s*[｜|／/]\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -・,，。")
    if len(text) <= 64:
        return text
    cut = text[:64]
    boundary = max(cut.rfind(" "), cut.rfind("・"))
    if boundary >= 42:
        cut = cut[:boundary]
    return cut.rstrip(" -・,，。") + "…"


def product_identity_html(item: dict, category: dict, name_class: str = "product-name") -> str:
    brand = product_brand(item["name"])
    brand_html = f'<span class="brand-chip">{html.escape(brand)}</span>' if brand else ""
    spec = html.escape(quantity_text(item, category["id"]))
    short_name = compact_product_name(item["name"])
    return f"""<div class="identity-line">{brand_html}<span class="spec-chip">{spec}</span></div>
<strong class="{name_class}" title="{html.escape(item['name'], quote=True)}">{html.escape(short_name)}</strong>"""


def price_history_badges(item: dict) -> str:
    history = item.get("price_history") or {}
    previous = history.get("previous_price")
    parts = []
    delta = history.get("price_delta")
    if previous is not None and delta is not None and delta < 0:
        label = history.get("previous_label") or "前回比"
        parts.append(
            f'<span class="trend-badge drop">↓ ¥{abs(int(delta)):,} {html.escape(label)}</span>'
        )
    if history.get("is_30d_low"):
        parts.append('<span class="trend-badge low">30日最安</span>')
    return "".join(parts)


def price_signal(item: dict) -> tuple[str, str, str]:
    history = item.get("price_history") or {}
    observed = int(history.get("observed_days") or 0)
    if observed < 2:
        return "履歴蓄積中", "neutral", "2回以上の取得後に履歴ベースで判定します。"

    series = history.get("series_30d") or []
    current_unit = float(series[-1]["unit"]) if series else None
    low = history.get("lowest_30d_unit")
    delta = history.get("price_delta")

    if history.get("is_30d_low") and delta is not None and delta < 0:
        return "買い時寄り", "buy", "値下がりし、30日内の最安水準です。"
    if delta is not None and delta < 0:
        return "買い時寄り", "buy", "前回取得時より価格が下がっています。"
    if current_unit is not None and low:
        premium = (current_unit - float(low)) / float(low)
        if premium >= 0.05:
            return "様子見寄り", "wait", "30日内の最安水準より5%以上高い状態です。"
    return "相場圏", "neutral", "直近履歴では大きな割高・値下がりは確認できません。"


def history_range_panel(series: list[dict], label: str, tone: str, visible: bool) -> str:
    values = [float(point.get("unit") or 0) for point in series if point.get("unit") is not None]
    if not values:
        return ""
    current = values[-1]
    low_index = min(range(len(values)), key=lambda i: values[i])
    high_index = max(range(len(values)), key=lambda i: values[i])
    low = values[low_index]
    high = values[high_index]
    width, height, pad = 180.0, 64.0, 6.0
    span = high - low
    points = []
    circles = []
    for idx, value in enumerate(values):
        x = pad + (width - pad * 2) * idx / max(1, len(values) - 1)
        y = height / 2 if span < 1e-9 else pad + (height - pad * 2) * (high - value) / span
        points.append(f"{x:.1f},{y:.1f}")
        if idx == len(values) - 1:
            circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2"/>')
    low_date = str(series[low_index].get("date") or "")[5:].replace("-", "/")
    high_date = str(series[high_index].get("date") or "")[5:].replace("-", "/")
    spread = high - low
    hidden = "" if visible else " hidden"
    return f"""<div class="history-range-panel" data-history-panel="{label}"{hidden}>
<div class="history-stats history-stats-4">
<div><span>現在</span><b>{yen(current)}</b></div>
<div><span>最安</span><b>{yen(low)}</b><small>{html.escape(low_date)}</small></div>
<div><span>最高</span><b>{yen(high)}</b><small>{html.escape(high_date)}</small></div>
<div><span>値幅</span><b>{yen(spread)}</b></div>
</div>
<svg class="sparkline {tone}" viewBox="0 0 180 64" role="img" aria-label="{label}価格推移">
<line x1="6" y1="58" x2="174" y2="58" class="spark-grid"/>
<polyline points="{' '.join(points)}" fill="none" vector-effect="non-scaling-stroke"/>
{''.join(circles)}
</svg></div>"""


def sparkline_svg(item: dict) -> str:
    history = item.get("price_history") or {}
    series_30 = history.get("series_30d") or []
    series_7 = history.get("series_7d") or []
    observed = int(history.get("observed_days") or 0)
    current = float(series_30[-1]["unit"]) if series_30 else None

    if len(series_30) < 2:
        current_html = yen(current) if current is not None else "—"
        return f"""<div class="history-card history-pending">
<div class="history-head"><strong>価格履歴</strong><span>{observed}回取得</span></div>
<div class="history-stats"><div><span>現在</span><b>{current_html}</b></div><div><span>7日</span><b>蓄積中</b></div><div><span>30日</span><b>蓄積中</b></div></div>
<div class="sparkline-empty">次回取得後からグラフを表示</div></div>"""

    _, tone, _ = price_signal(item)
    trend = history.get("trend_7d") or "stable"
    trend_label = {"down": "最近下落", "up": "最近上昇", "stable": "最近安定"}.get(trend, "最近安定")
    trend_tone = {"down": "down", "up": "up", "stable": "stable"}.get(trend, "stable")
    panel7 = history_range_panel(series_7, "7日", tone, True)
    panel30 = history_range_panel(series_30, "30日", tone, False)
    return f"""<div class="history-card" data-history-card>
<div class="history-head"><strong>価格履歴</strong><span>{observed}回取得</span></div>
<div class="history-toolbar"><div class="history-tabs">
<button type="button" class="selected" data-history-range="7日">7日</button>
<button type="button" data-history-range="30日">30日</button>
</div><span class="history-trend {trend_tone}">{html.escape(trend_label)}</span></div>
{panel7}{panel30}
</div>"""

def price_signal_html(item: dict) -> str:
    label, tone, reason = price_signal(item)
    return f"""<div class="buy-signal {tone}">
<span>{html.escape(label)}</span><small>{html.escape(reason)}</small>
</div>"""


def product_history_details(item: dict, label: str = "価格のうごきを見る") -> str:
    return f"""<details class="product-extra" data-product-extra>
<summary>{html.escape(label)} <span>＋</span></summary>
<div class="product-extra-body">{sparkline_svg(item)}{price_signal_html(item)}</div>
</details>"""


def service_shortcuts_html() -> str:
    return f"""<nav class="service-shortcuts" aria-label="主要メニュー">
<a href="{SITE_URL}"><span>⌂</span>トップ</a>
<a href="{SITE_URL}deals/"><span>↓</span>今日のお買い得</a>
<a href="{SITE_URL}saved/">買い物メモ</a>
</nav>"""


def shopping_journey_html() -> str:
    return """<section class="journey-strip" aria-label="商品の選び方">
<div><span>1</span><strong>候補を見る</strong><small>単価と総額を確認</small></div>
<i>→</i><div><span>2</span><strong>比較する</strong><small>最大3商品まで</small></div>
<i>→</i><div><span>3</span><strong>あとで見る</strong><small>価格変化を追える</small></div>
<i>→</i><div><span>4</span><strong>楽天で確認</strong><small>購入前に最終価格確認</small></div>
</section>"""


def cta_copy(item: dict, context: str, rank: int | None = None) -> tuple[str, str]:
    history = item.get("price_history") or {}
    delta = history.get("price_delta")
    if history.get("is_30d_low") and delta is not None and delta < 0:
        return "30日最安を楽天で確認 →", "history_low"
    if delta is not None and delta < 0:
        return "値下がり価格を楽天で確認 →", "price_drop"
    if context == "top3" and rank == 1:
        return "最安候補を楽天で確認 →", "rank1"
    if context == "finder":
        return "この候補を楽天で確認 →", "finder"
    if context == "deal":
        return "値下がり商品を楽天で確認 →", "deal"
    return "楽天で価格を確認 →", "standard"


def cta_attrs(variant: str) -> str:
    return f'data-cta-variant="{html.escape(variant, quote=True)}"'



def deal_entries(results: dict) -> tuple[list[tuple], bool]:
    deals = []
    has_history = False
    for category in CATEGORIES:
        included, _ = results.get(category["id"], ([], []))
        for item in included:
            history = item.get("price_history") or {}
            if history.get("previous_price") is not None:
                has_history = True
            delta = history.get("price_delta")
            if delta is None or delta >= 0:
                continue
            percent = abs(float(history.get("percent_delta") or 0))
            deals.append((
                0 if history.get("is_30d_low") else 1,
                -percent,
                delta,
                category,
                item,
            ))
    deals.sort(key=lambda x: (x[0], x[1], x[2], x[4]["unit_prices"][x[3]["primary"]]))
    return deals, has_history


def deal_card_html(category: dict, item: dict, position: str = "today_deal") -> str:
    history = item["price_history"]
    primary = item["unit_prices"][category["primary"]]
    image = (
        f'<img src="{html.escape(item["image"], quote=True)}" alt="" width="320" height="320" loading="lazy">'
        if item["image"] else category_illustration(category["id"], True)
    )
    label = history.get("previous_label") or "前回比"
    cta_label, cta_variant = cta_copy(item, "deal")
    return f"""<article class="deal-card">
<div class="deal-media">{image}</div>
<div class="deal-copy">
<div class="deal-top"><span>{category["emoji"]} {html.escape(category["name"])}</span>{price_history_badges(item)}</div>
{product_identity_html(item, category, "deal-name")}
<div class="deal-price-row"><span class="deal-was">¥{history["previous_price"]:,}</span><strong>¥{item["price"]:,}</strong></div>
<div class="deal-saving">{html.escape(label)} ¥{abs(int(history["price_delta"])):,}安い</div>
<div class="deal-unit">{yen(primary)} <small>{html.escape(category["primary_label"])}</small></div>
{product_history_details(item, "価格のうごきを見る")}
{product_action_buttons(item, category, primary)}
<a class="cta" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-position="{html.escape(position, quote=True)}" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="" data-metric="{category['primary']}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}" {cta_attrs(cta_variant)}>{html.escape(cta_label)}</a>
</div></article>"""


def deals_page(results: dict, updated: datetime) -> str:
    deals, has_history = deal_entries(results)
    head = page_head(
        "今日のお買い得｜食品コスパ比較",
        "前回取得時より実際に値下がりした食品だけを、価格履歴と単価で確認できます。",
        f"{SITE_URL}deals/",
        breadcrumb_json_ld([
            ("食品コスパ比較", SITE_URL),
            ("今日のお買い得", f"{SITE_URL}deals/"),
        ]),
    )
    if deals:
        cards = "".join(deal_card_html(category, item, "deals_page") for _, _, _, category, item in deals)
        body = f"""<section class="section deal-section">
<div class="section-kicker">TODAY’S PICKS</div>
<h2>実際に値下がりした商品 {len(deals)}件</h2>
<p class="sub">同じ楽天商品IDかつ同じ容量構成だけを過去価格と比較しています。</p>
<div class="deal-grid">{cards}</div>
</section>"""
    else:
        message = (
            "価格履歴を蓄積中です。翌日以降の更新から値下がり判定が育っていきます。"
            if not has_history else
            "前回取得価格より下がった商品はありません。無理に『お買い得』を作らず、値下がりが確認できた時だけ掲載します。"
        )
        body = f"""<section class="section explain"><h2>現在、掲載できる値下がり商品はありません</h2>
<p>{html.escape(message)}</p></section>"""
    return head + f"""<header><div class="wrap hero-layout">
<div><a class="brand" href="../">食品コスパ比較</a><div class="eyebrow">PRICE HISTORY</div>
<h1>今日のお買い得だけを見る。</h1>
<p class="lead">単価ランキングとは別に、前回取得時より実際に安くなった商品だけを集めます。</p>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST</p></div>
<div class="category-hero-art">{guide_mascot()}</div></div></header>
{service_shortcuts_html()}
<main class="wrap">{body}
<section class="section explain"><h2>「今は安め」の判定について</h2>
<p>未来の価格を予測するものではありません。実測履歴だけを使い、値下がり・30日内最安水準・過去30日との差から表示します。</p>
<p><a class="finder-go" href="../">トップへ戻る →</a></p></section>
{utility_panels_html()}</main><script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。価格は取得時点の参考情報です。</div></footer>
</body></html>"""



def today_deals_html(results: dict) -> str:
    deals, has_history = deal_entries(results)
    if not deals:
        title = "価格履歴を蓄積中です。" if not has_history else "今日の値下がりは見つかりませんでした。"
        text = (
            "今日から商品ごとの価格を記録します。翌日以降、同じ容量の商品だけを比較して値下がりを表示します。"
            if not has_history else
            "前回取得価格より下がった商品だけをここに表示します。値下がりがない日は無理におすすめを作りません。"
        )
        return f"""<section class="section deal-section">
<div class="section-kicker">TODAY’S PICKS</div><h2>今日のお買い得</h2>
<div class="deal-empty">{guide_mascot(True)}<div><strong>{title}</strong><p>{text}</p>
<a class="deal-more" href="deals/">価格履歴ページを見る →</a></div></div>
</section>"""

    cards = "".join(
        deal_card_html(category, item, "today_deal")
        for _, _, _, category, item in deals[:6]
    )
    return f"""<section class="section deal-section">
<div class="section-kicker">TODAY’S PICKS</div>
<h2>今日のお買い得</h2>
<p class="sub">前回取得時より実際に価格が下がった商品だけを表示。容量構成が変わった商品は比較しません。</p>
<div class="deal-grid">{cards}</div>
<a class="deal-more" href="deals/">値下がり商品をすべて見る →</a>
</section>"""

def shopping_bucket(item: dict, category_id: str) -> str:
    # Bottle volume alone does not describe how much needs to be stored.
    if category_id == "carbonated-water":
        return "small" if item["quantity"]["total_volume_ml"] <= 12000 else "large"
    return bucket(item, category_id)


def finder_pick_items(items: list[dict], category: dict, purpose: str) -> list[dict]:
    source = [x for x in items if x.get("postage_included")]
    if purpose in ("small", "storage", "large"):
        target = "large" if purpose == "large" else "small"
        source = [x for x in source if shopping_bucket(x, category["id"]) == target]
    metric = category["primary"]
    source.sort(key=lambda x: (x["price"], x["unit_prices"][metric]) if purpose in ("budget", "storage", "small") else (x["unit_prices"][metric], x["price"]))
    return source[:3]


def recommendation_reason(item: dict, category: dict, purpose: str, position: int) -> str:
    if purpose == "budget":
        return "支払総額を抑えやすい候補" if position == 1 else "商品価格が低めの候補"
    if purpose == "storage":
        return "合計量が少量側・商品価格が低い候補" if position == 1 else "合計量が少量側の候補"
    if purpose == "small":
        return "少量側から商品価格の低い順で選定"
    if purpose == "large":
        return "大容量側の中で単価が安い候補"
    return "この条件で単価が安い候補" if position == 1 else "同じ売り場で単価が低い候補"


def finder_product_card(item: dict, category: dict, position: int, purpose: str, reason_override: str = "") -> str:
    primary = item["unit_prices"][category["primary"]]
    image_url = item["image"] or ""
    if image_url.startswith("https://thumbnail.image.rakuten.co.jp/"):
        image_url = re.sub(r"([?&])_ex=\d+x\d+", r"\1_ex=640x640", image_url)
    image = (
        f'<img src="{html.escape(image_url, quote=True)}" alt="" width="320" height="320" loading="lazy">'
        if item["image"] else category_illustration(category["id"], True)
    )
    reason = reason_override or recommendation_reason(item, category, purpose, position)
    cta_label, cta_variant = cta_copy(item, "finder", position)
    return f"""<article class="finder-product discovery-product">
<div class="finder-product-media">{image}</div>
<div class="finder-product-copy">
<div class="finder-product-price">{yen(primary)} <small>{html.escape(category["primary_label"])}</small></div>
<span class="finder-product-rank">{html.escape(category["name"])}</span>
{product_identity_html(item, category, "finder-product-name")}
<div class="finder-product-meta">商品価格 ¥{item["price"]:,}<br>{html.escape(quantity_text(item, category["id"]))}</div>
<div class="shelf-shipping">送料込み確認済み</div>
<div class="trend-row">{price_history_badges(item)}</div>
<div class="finder-why"><span>なぜ？</span>{html.escape(reason)}</div>
{product_history_details(item)}
{product_action_buttons(item, category, primary)}
<a class="cta" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-position="quick_finder_result" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{position}" data-metric="{category['primary']}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}" {cta_attrs(cta_variant)}>{html.escape(cta_label)}</a>
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
<button type="button" class="utility-btn" data-save-product {attrs}>＋ 買い物メモ</button>
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
        f"""<div class="insight-card"><span>大容量側の注目</span><strong>{yen(large_best["unit_prices"][metric])}</strong><small>{html.escape(category["primary_label"])}</small></div>"""
        if large_best else
        """<div class="insight-card"><span>大容量側</span><strong>—</strong><small>現在候補なし</small></div>"""
    )
    return f"""<section class="section insight-section">
<div class="section-kicker">PRICE SNAPSHOT</div>
<h2>いまの価格差をひと目で。</h2>
<div class="insight-grid">
<div class="insight-card"><span>1位と3位の差</span><strong>{yen(diff)}</strong><small>{html.escape(category["primary_label"])}の差</small></div>
<div class="insight-card"><span>支払総額が低い候補</span><strong>¥{cheapest_total["price"]:,}</strong><small>{html.escape(quantity_text(cheapest_total, category["id"]))}</small></div>
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
    return f"""<button class="saved-fab" type="button" data-open-saved>＋ 買い物メモ <span data-saved-count>0</span></button>
<div class="compare-bar" data-compare-bar hidden>
<div><strong>比べるかご</strong><span data-compare-summary>0/3</span></div>
<div class="compare-bar-items" data-compare-bar-items></div>
<button type="button" class="compare-open" data-open-compare>選んだ商品を比べる</button>
<button type="button" class="compare-memo" data-open-saved>メモ</button>
<button type="button" class="compare-clear" data-clear-compare>クリア</button>
</div>
<div class="utility-modal" data-saved-modal role="dialog" aria-modal="true" aria-labelledby="saved-title" hidden>
<div class="utility-sheet">
<button class="utility-close" type="button" data-close-saved aria-label="買い物メモを閉じる">×</button>
<div class="section-kicker">SAVED</div><h2 id="saved-title">買い物メモ</h2>
<p><a class="saved-watch-link" href="{SITE_URL}saved/">保存商品の値下がり・価格履歴を見る →</a></p>
<div data-saved-list></div>
</div></div>
<div class="site-toast" data-toast role="status" aria-live="polite" hidden></div>
<div class="utility-modal" data-compare-modal role="dialog" aria-modal="true" aria-labelledby="compare-title" hidden>
<div class="utility-sheet utility-sheet-wide">
<button class="utility-close" type="button" data-close-compare aria-label="商品比較を閉じる">×</button>
<div class="section-kicker">COMPARE</div><h2 id="compare-title">選んだ商品を比較</h2>
<div data-compare-table></div>
</div></div>"""



def top3_html(items: list[dict], category: dict) -> str:
    if not items:
        return ""
    cards = []
    labels = ["いまの最安", "2位", "3位"]
    medal = ["01", "02", "03"]
    best_primary = items[0]["unit_prices"][category["primary"]]
    for index, item in enumerate(items[:3]):
        rank = index + 1
        primary = item["unit_prices"][category["primary"]]
        diff = max(0, primary - best_primary)
        diff_text = "最安" if rank == 1 else f"最安との差 +{yen(diff)}"
        cta_label, cta_variant = cta_copy(item, "top3", rank)
        image = (
            f'<img class="podium-img" src="{html.escape(item["image"], quote=True)}" alt="" width="320" height="320" loading="lazy">'
            if item["image"] else category_illustration(category["id"], True)
        )
        cards.append(f"""<article class="podium-card rank-{rank}">
<div class="podium-head"><span class="podium-medal">{medal[index]}</span><span>{labels[index]}</span></div>
<div class="podium-badges">{item_badges(item, category, rank)}</div>
<div class="podium-media">{image}</div>
{product_identity_html(item, category, "podium-name")}
<div class="podium-unit">{yen(primary)}</div>
<div class="podium-label">{html.escape(category["primary_label"])}</div>
<div class="trend-row">{price_history_badges(item)}</div>
<div class="podium-diff">{html.escape(diff_text)}</div>
<div class="podium-detail">{html.escape(quantity_text(item, category["id"]))} ・ ¥{item["price"]:,}</div>
{product_history_details(item)}
{product_action_buttons(item, category, primary)}
<a class="cta podium-cta" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-position="top3_card" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{category['primary']}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}" {cta_attrs(cta_variant)}>{html.escape(cta_label)}</a>
</article>""")
    return f"""<section class="section podium-section">
<div class="section-kicker">まずはここから</div>
<h2>この売り場のおすすめ棚 <small>送料込み TOP{min(3, len(items))}</small></h2>
<p class="sub">現在取得できた商品の中で、{html.escape(category["primary_label"])}が安い順です。</p>
<div class="podium-grid">{''.join(cards)}</div>
</section>"""


SHOPPING_INTENTS = {
    "cheap": ("今日、単価の良いものを", "値下がりと各売り場の単価上位から"),
    "large": ("まとめてストックしたい", "大容量側の、単価が低い候補へ"),
    "small": ("少量で気軽に買いたい", "少量側の、商品価格が低い候補へ"),
    "budget": ("支払総額を抑えたい", "各売り場で、商品価格が低い候補へ"),
    "storage": ("収納する量を抑えたい", "合計量が少量側の候補へ"),
    "known": ("買うものは決まっている", "食品の売り場を選んで比べる"),
}


def cross_shelf_items(results: dict, purpose: str) -> list[tuple]:
    # One candidate per aisle: never rank unlike units against one another.
    selected = []
    deals, _ = deal_entries(results)
    for category in CATEGORIES:
        items, _ = results.get(category["id"], ([], []))
        picks = finder_pick_items(items, category, purpose)
        if purpose == "cheap":
            drops = [entry[4] for entry in deals if entry[3]["id"] == category["id"]]
            if drops:
                picks = drops
        if picks:
            selected.append((category, picks[0]))
    return selected


def market_shelf_html(entries: list[tuple], title: str, shelf_id: str, purpose: str = "cheap", note: str = "") -> str:
    cards = []
    for i, (category, item) in enumerate(entries, 1):
        delta = (item.get("price_history") or {}).get("price_delta")
        uses_drop = purpose == "cheap" and shelf_id in ("today", "finder-all-cheap")
        reason = "前回取得時より価格が下がった掲載商品" if uses_drop and delta is not None and delta < 0 else ""
        cards.append(finder_product_card(item, category, i, purpose, reason))
    cards = "".join(cards)
    if not shelf_id.startswith("finder-"):
        cards = cards.replace('data-position="quick_finder_result"', 'data-position="market_shelf"')
    if not cards:
        cards = '<p class="shelf-empty">この条件の掲載候補は現在ありません。別の買い方や売り場も見てみましょう。</p>'
    return f'''<section class="market-shelf" data-market-shelf="{shelf_id}">
<div class="shelf-heading"><span class="section-kicker">MARKET SHELF</span><h3>{html.escape(title)}</h3></div>
<p class="sub">{html.escape(note)}</p><p class="shelf-mobile-hint">棚を横に見る →</p><div class="finder-products">{cards}</div></section>'''


def today_market_html(results: dict) -> str:
    entries = cross_shelf_items(results, "cheap")
    deals, has_history = deal_entries(results)
    history_note = "実際の値下がりを確認した商品と、各売り場の単価上位から。" if deals else "今回は値下がり候補なし。各売り場の単価上位から。" if has_history else "価格履歴を蓄積中。今は各売り場の単価上位から。"
    return f'''<section class="section deal-section" id="today-market">
<div class="section-kicker">A LITTLE DISCOVERY, TODAY</div><h2>今日のマルシェ、まずはこの棚から。</h2>
{market_shelf_html(entries, "本日のおすすめ棚", "today", note=history_note+" 食品をまたぐ順位・品質のおすすめではありません。")}
<a class="deal-more" href="deals/" data-start-route="deals">今日のお買い得・価格履歴を見る →</a>
</section>'''


def discovery_shelves_html(results: dict) -> str:
    return '<section class="section discovery-shelves"><div class="section-kicker">A WALK THROUGH THE MARKET</div><h2>こんな買い方も、いいかもしれない。</h2>'+''.join(
        market_shelf_html(cross_shelf_items(results, key), title, "discover-"+key, key, note)
        for key,title,note in [("large","まとめて備える棚","各売り場の大容量側から単価の低い候補を1つずつ。保管場所・消費量・賞味期限は購入前に確認してください。"), ("small","小さく買ってみる棚","各売り場の少量側から商品価格の低い候補を1つずつ。異なる食品の単価は順位づけしません。")])+'</section>'


def choice_finder_html(results: dict) -> str:
    choices = "".join(f'''<button class="finder-category {c['id']}" type="button" aria-pressed="false" data-finder-category="{c['id']}" data-finder-name="{html.escape(c['name'], quote=True)}"><span class="finder-art">{category_illustration(c['id'], True)}</span><span>{html.escape(c['name'])}</span></button>''' for c in CATEGORIES)
    intents = ''.join(f'''<button type="button" data-finder-purpose="{key}" aria-pressed="false"><span class="intent-number">0{i}</span><span><strong>{label}</strong><small>{hint}</small></span><span aria-hidden="true">↗</span></button>''' for i,(key,(label,hint)) in enumerate(((k,v) for k,v in SHOPPING_INTENTS.items() if k in ("large","small","budget","storage")),1))
    routes = ''.join(f'<button type="button" data-entry-route="{key}" aria-pressed="false"><span class="intent-number">0{i}</span><span><strong>{label}</strong><small>{hint}</small></span><span aria-hidden="true">→</span></button>' for i,(key,label,hint) in enumerate([('deal','お得なものから見つけたい','今日いい値段の商品を見たい'),('advisor','わたしに合う買い方で探したい','ストック？ 少量？ 支出を抑える？'),('known','買うものは決まっている','食品からすぐ比較したい')],1))
    panels=[]
    for purpose in ("cheap","small","large","budget","storage"):
        label=SHOPPING_INTENTS[purpose][0]
        entries=cross_shelf_items(results,purpose)
        panels.append(f'<div class="finder-picks" data-finder-picks="all:{purpose}" hidden>'+market_shelf_html(entries,label,"finder-all-"+purpose,purpose,"送料込み確認済み。各売り場から1候補ずつ。単位が異なる食品を順位づけしません。")+'</div>')
        for c in CATEGORIES:
            picks=finder_pick_items(results.get(c['id'],([],[]))[0],c,purpose)
            entries=[(c,x) for x in picks]
            note='掲載候補内の比較。少量の基準：ご飯24食以下、米5kg以下、炭酸水合計12L以下、オートミール1kg以下。収納寸法の判定ではありません。'
            panels.append(f'<div class="finder-picks" data-finder-picks="{c["id"]}:{purpose}" hidden>'+market_shelf_html(entries,c['name']+' · '+label,'finder-'+c['id']+'-'+purpose,purpose,note)+f'<a class="finder-all" href="categories/{c["id"]}/?pick={purpose}#included">この売り場の商品一覧へ →</a></div>')
    return f'''<section class="section finder" id="quick-finder" data-finder>
<div class="finder-intro"><div><div class="section-kicker">LET’S FIND YOUR SHELF</div><h2>今日は、どう探す？</h2><p class="sub">買うものが決まっていなくても大丈夫。気分に合う棚から見ていきましょう。</p></div><div class="finder-guide">{guide_mascot(True)}<span>一緒に、棚を探しましょう。</span></div></div>
<div class="finder-stage" data-finder-route-stage><div class="finder-options finder-route-options">{routes}</div></div>
<div class="finder-stage" data-finder-purpose-stage hidden><button class="finder-back" type="button" data-finder-back>← 探し方に戻る</button><div class="finder-question"><span>YOUR SHOPPING</span><strong>どんな量・出費で買いたい？</strong></div><div class="finder-options finder-purpose-options">{intents}</div></div>
<p class="finder-status" data-finder-status role="status" aria-live="polite"></p>
<div class="finder-stage" data-finder-category-stage hidden><button class="finder-back" type="button" data-finder-back>← 探し方に戻る</button><div class="finder-question"><span>STEP 2</span><strong>何を探してる？</strong></div><div class="finder-options finder-category-options">{choices}</div></div>
<div class="finder-stage finder-result-stage" data-finder-result-stage hidden><div class="finder-result-actions"><button class="finder-back" type="button" data-finder-reset>← 探し方を変える</button><button class="finder-back" type="button" data-finder-narrow>売り場を絞る →</button></div>{''.join(panels)}</div></section>'''


def item_badges(item: dict, category: dict, rank: int) -> str:
    badges = []
    if rank == 1 and item["postage_included"]:
        badges.append('<span class="tag best">最安候補</span>')
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
<div class="flow-card"><div class="flow-icon"></div><strong>1. 商品情報を取得</strong><p>価格・容量・個数・送料条件を楽天の商品情報から確認。</p></div>
<div class="flow-arrow">→</div>
<div class="flow-card"><div class="flow-icon"></div><strong>2. 同じ単位にそろえる</strong><p>1食・1kg・1L・100gあたりへ換算して比較できる形に。</p></div>
<div class="flow-arrow">→</div>
<div class="flow-card"><div class="flow-icon"></div><strong>3. 安い順で見る</strong><p>数量が曖昧な商品は外し、送料込みの商品を先にランキング。</p></div>
</div>
</section>"""


CSS = (Path(__file__).parent / "marche.css").read_text(encoding="utf-8") + (Path(__file__).parent / "market.css").read_text(encoding="utf-8")


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
  const pos=a.dataset.position||'comparison_table';
  const x={affiliate:'rakuten',conversion_source:pos,category_id:a.dataset.category,product_id:a.dataset.productId,product_name:a.dataset.productName,rank:a.dataset.rank,comparison_metric:a.dataset.metric,unit_price:Number(a.dataset.unitPrice||0),shipping_status:a.dataset.shipping,click_position:pos,cta_variant:a.dataset.ctaVariant||'standard',cta_text:(a.textContent||'').trim(),page_path:location.pathname,link_url:a.href};
  send('product_result_click',x);send('affiliate_click',x)
});
document.querySelectorAll('[data-start-route]').forEach(a=>a.addEventListener('click',()=>send('home_start_route',{route:a.dataset.startRoute||''})));
document.querySelectorAll('[data-product-extra]').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)send('product_detail_open',{page_path:location.pathname})}));
document.querySelectorAll('[data-sort]').forEach(s=>s.addEventListener('change',()=>{
  const root=s.closest('[data-comparison]'),body=root.querySelector('tbody'),rows=[...body.querySelectorAll('tr')],m=s.value;
  rows.sort((a,b)=>Number(a.dataset[m]||Infinity)-Number(b.dataset[m]||Infinity));
  const base=Number(root.dataset.startRank||1);
  rows.forEach((r,i)=>{
    const n=base+i,rankCell=r.querySelector('[data-rank]'),rankSpan=rankCell?.querySelector('.rank');
    if(rankSpan){rankSpan.textContent=n;rankSpan.classList.toggle('top',n<=3)}
    const link=r.querySelector('a[data-affiliate]');if(link)link.dataset.rank=String(n);
    body.appendChild(r)
  });
  send('comparison_sort',{category_id:s.dataset.category,comparison_metric:m})
}));
const applyFilters=root=>{
  const size=root.querySelector('[data-filter]')?.value||'all';
  const term=(root.querySelector('[data-search]')?.value||'').trim().toLowerCase();
  let shown=0;
  root.querySelectorAll('tbody tr').forEach(r=>{
    const sizeOk=size==='all'||(root.dataset.shoppingIntent?r.dataset.shoppingBucket:r.dataset.bucket)===size;
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
const shelfSeen=new WeakSet();
const shelfView=el=>{if(!el||shelfSeen.has(el)||el.closest('[hidden]'))return;shelfSeen.add(el);send('market_shelf_view',{shelf_id:el.dataset.marketShelf,product_count:el.querySelectorAll('[data-affiliate]').length})};
if(!('IntersectionObserver' in window))document.querySelectorAll('[data-market-shelf]').forEach(shelfView);
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting)shelfView(entry.target)}),{threshold:.1});document.querySelectorAll('[data-market-shelf]').forEach(el=>observer.observe(el))}
document.addEventListener('click',e=>{const a=e.target.closest('a[data-affiliate]');const shelf=a?.closest('[data-market-shelf]');if(shelf)send('market_shelf_product_click',{shelf_id:shelf.dataset.marketShelf,category_id:a.dataset.category,product_id:a.dataset.productId,cta_variant:a.dataset.ctaVariant})});
const finder=document.querySelector('[data-finder]');
if(finder){
  let category='all',purpose='',intent='',route='';
  const routeStage=finder.querySelector('[data-finder-route-stage]');
  const categoryStage=finder.querySelector('[data-finder-category-stage]'),purposeStage=finder.querySelector('[data-finder-purpose-stage]'),resultStage=finder.querySelector('[data-finder-result-stage]'),status=finder.querySelector('[data-finder-status]');
  const show=el=>{el.hidden=false;const first=el.querySelector('button');first?.focus({preventScroll:true});const top=el.getBoundingClientRect().top;if(top<0||top>window.innerHeight*.65)el.scrollIntoView?.({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches?'instant':'smooth'})};
  const hide=el=>el.hidden=true;
  const results=()=>{
    hide(routeStage);hide(purposeStage);hide(categoryStage);show(resultStage);
    let current;
    finder.querySelectorAll('[data-finder-picks]').forEach(panel=>{panel.hidden=panel.dataset.finderPicks!==category+':'+purpose;if(!panel.hidden)current=panel});
    const count=current?.querySelectorAll('[data-affiliate]').length||0;
    status.textContent=count?'それなら、この棚から。 '+count+'件の候補があります。':'この条件の候補は現在ありません。別の買い方も見てみましょう。';
    send('finder_complete',{category_id:category,shopping_intent:intent,product_count:count});
    send('quick_finder_complete',{category_id:category,finder_purpose:purpose});
    if(!('IntersectionObserver' in window))shelfView(current?.querySelector('[data-market-shelf]'));
  };
  const reset=()=>{purpose='';category='all';route='';show(routeStage);hide(purposeStage);hide(categoryStage);hide(resultStage);status.textContent='';finder.querySelectorAll('[data-finder-picks]').forEach(x=>x.hidden=true);finder.querySelectorAll('[aria-pressed]').forEach(x=>x.setAttribute('aria-pressed','false'));finder.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'))};
  const selectRoute=key=>{
    route=key;category='all';status.textContent='';hide(routeStage);hide(purposeStage);hide(categoryStage);hide(resultStage);
    finder.querySelectorAll('[data-entry-route]').forEach(x=>{x.classList.toggle('selected',x.dataset.entryRoute===key);x.setAttribute('aria-pressed',String(x.dataset.entryRoute===key))});
    send('entry_route_select',{entry_route:key});
    if(key==='advisor'){show(purposeStage);return}
    intent=key==='deal'?'cheap':'known';purpose='cheap';send('shopping_intent_select',{shopping_intent:intent});
    if(key==='known'){show(categoryStage);status.textContent='いつもの食品を、売り場から選びましょう。'}else results();
  };
  finder.querySelectorAll('[data-entry-route]').forEach(btn=>btn.addEventListener('click',()=>selectRoute(btn.dataset.entryRoute)));
  document.querySelector('[data-hero-known]')?.addEventListener('click',()=>selectRoute('known'));
  document.querySelector('[data-hero-primary]')?.addEventListener('click',()=>{reset();send('hero_primary_cta',{destination:'quick-finder'})});
  finder.querySelectorAll('[data-finder-purpose]').forEach(btn=>btn.addEventListener('click',()=>{
    purpose=btn.dataset.finderPurpose;intent=purpose;category='all';
    finder.querySelectorAll('[data-finder-purpose]').forEach(x=>{x.classList.toggle('selected',x===btn);x.setAttribute('aria-pressed',String(x===btn))});
    send('shopping_intent_select',{shopping_intent:intent});results();
  }));
  finder.querySelectorAll('[data-finder-category]').forEach(btn=>btn.addEventListener('click',()=>{category=btn.dataset.finderCategory;finder.querySelectorAll('[data-finder-category]').forEach(x=>{x.classList.toggle('selected',x===btn);x.setAttribute('aria-pressed',String(x===btn))});send('quick_finder_category',{category_id:category});send('category_select_after_intent',{category_id:category,shopping_intent:intent});results()}));
  finder.querySelector('[data-finder-narrow]')?.addEventListener('click',()=>{hide(resultStage);show(categoryStage);status.textContent='この買い方のまま、売り場を選べます。'});
  finder.querySelectorAll('[data-finder-back]').forEach(btn=>btn.addEventListener('click',reset));
  finder.querySelector('[data-finder-reset]')?.addEventListener('click',reset);
}
const pick=new URLSearchParams(location.search).get('pick');
if(pick&&document.querySelector('[data-comparison]')){
  const root=document.querySelector('[data-comparison]');
  const filter=root.querySelector('[data-filter]');
  const sort=root.querySelector('[data-sort]');
  if(filter&&(pick==='small'||pick==='large'||pick==='storage')){root.dataset.shoppingIntent=pick;filter.value=pick==='storage'?'small':pick;if(filter.dataset.category==='carbonated-water'){filter.querySelector('[value=small]').textContent='合計12L以下';filter.querySelector('[value=large]').textContent='合計12L超'}const label=root.querySelector('[data-intent-note]');if(label)label.textContent='買い方で絞った一覧：少量側 / 大容量側は合計量を基準にしています。'}
  if(filter&&pick==='storage')filter.value='small';
  if(sort&&(pick==='budget'||pick==='storage')){sort.value='price';sort.dispatchEvent(new Event('change'))}
  const details=root.closest('details');if(details)details.open=true;
  applyFilters(root);
  send('quick_finder_landing',{category_id:filter?.dataset.category||'',finder_purpose:pick})
}

document.addEventListener('click',e=>{
  const rangeBtn=e.target.closest('[data-history-range]');
  if(!rangeBtn)return;
  const card=rangeBtn.closest('[data-history-card]');if(!card)return;
  const range=rangeBtn.dataset.historyRange;
  card.querySelectorAll('[data-history-range]').forEach(btn=>btn.classList.toggle('selected',btn===rangeBtn));
  card.querySelectorAll('[data-history-panel]').forEach(panel=>panel.hidden=panel.dataset.historyPanel!==range);
  send('price_history_range_change',{range_value:range,page_path:location.pathname})
});
const SAVED_KEY='food_cost_saved_v1',COMPARE_KEY='food_cost_compare_v1';
const readList=key=>{try{const v=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(v)?v:[]}catch(e){return[]}};
const writeList=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch(e){}};
const itemKey=x=>x.category+'|'+x.id;
const fromButton=btn=>({
  id:btn.dataset.productId||'',
  name:btn.dataset.productName||'',
  category:btn.dataset.productCategory||'',
  categoryName:btn.dataset.productCategoryName||'',
  price:Number(btn.dataset.productPrice||0),
  unit:Number(btn.dataset.productUnit||0),
  unitLabel:btn.dataset.productUnitLabel||'',
  quantity:btn.dataset.productQuantity||'',
  url:btn.dataset.productUrl||'',
  image:btn.dataset.productImage||''
});
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const money=n=>'¥'+Number(n||0).toLocaleString('ja-JP',{maximumFractionDigits:1});
let saved=readList(SAVED_KEY),compared=readList(COMPARE_KEY).slice(0,3);
const toastEl=document.querySelector('[data-toast]');
let toastTimer;
const toast=message=>{
  if(!toastEl)return;
  toastEl.textContent=message;toastEl.hidden=false;
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>toastEl.hidden=true,1800)
};
const syncUtilityButtons=()=>{
  const savedKeys=new Set(saved.map(itemKey)),compareKeys=new Set(compared.map(itemKey));
  document.querySelectorAll('[data-save-product]').forEach(btn=>{
    const active=savedKeys.has((btn.dataset.productCategory||'')+'|'+(btn.dataset.productId||''));
    btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));btn.textContent=active?'✓ メモ済み':'＋ 買い物メモ'
  });
  document.querySelectorAll('[data-compare-product]').forEach(btn=>{
    const active=compareKeys.has((btn.dataset.productCategory||'')+'|'+(btn.dataset.productId||''));
    btn.classList.toggle('active',active);btn.setAttribute('aria-pressed',String(active));btn.textContent=active?'✓ 比較中':'＋ 比較する'
  });
  const count=document.querySelector('[data-saved-count]');if(count)count.textContent=String(saved.length)
};
const renderSaved=()=>{
  const root=document.querySelector('[data-saved-list]');if(!root)return;
  if(!saved.length){root.innerHTML='<div class="utility-empty">保存した商品はまだありません。</div>';return}
  root.innerHTML=saved.map(x=>'<div class="saved-item">'+
    (x.image?'<img src="'+esc(x.image)+'" alt="">':'<div></div>')+
    '<div><strong>'+esc(x.name)+'</strong><small>'+esc(x.categoryName)+' ・ '+money(x.unit)+' '+esc(x.unitLabel)+' ・ '+money(x.price)+'</small><a href="'+esc(x.url)+'" target="_blank" rel="nofollow sponsored noopener">楽天で見る →</a></div>'+
    '<button type="button" data-remove-saved="'+esc(itemKey(x))+'" aria-label="保存から削除">削除</button></div>').join('')
};
const renderCompare=()=>{
  const root=document.querySelector('[data-compare-table]');if(!root)return;
  if(!compared.length){root.innerHTML='<div class="utility-empty">「比較する」から最大3商品を選べます。</div>';return}
  const cells=(label,fn)=>'<tr><td>'+esc(label)+'</td>'+compared.map(x=>'<td>'+fn(x)+'</td>').join('')+'</tr>';
  root.innerHTML='<div class="compare-table"><table><thead><tr><th>比較項目</th>'+
    compared.map(x=>'<th>'+esc(x.name)+'</th>').join('')+
    '</tr></thead><tbody>'+
    cells('商品価格',x=>money(x.price))+
    cells('内容量',x=>esc(x.quantity))+
    cells(compared[0]&&compared[0].unitLabel?compared[0].unitLabel:'主要単価',x=>'<strong>'+money(x.unit)+'</strong>')+
    cells('販売先',x=>'<a href="'+esc(x.url)+'" target="_blank" rel="nofollow sponsored noopener">楽天で見る →</a>')+
    '</tbody></table></div>'
};
const syncCompareBar=()=>{
  const bar=document.querySelector('[data-compare-bar]');if(!bar)return;
  bar.hidden=!compared.length;
  document.body.classList.toggle('has-compare',Boolean(compared.length));
  const summary=bar.querySelector('[data-compare-summary]');if(summary)summary.textContent=compared.length+'/3';
  const items=bar.querySelector('[data-compare-bar-items]');
  if(items)items.innerHTML=compared.map(x=>'<span class="compare-chip">'+(x.image?'<img src="'+esc(x.image)+'" alt="">':'')+'<span>'+esc(x.name)+'</span><button type="button" class="compare-remove" data-remove-compare="'+esc(itemKey(x))+'" aria-label="'+esc(x.name)+'を比較から外す">×</button></span>').join('');
  const open=bar.querySelector('[data-open-compare]');if(open)open.textContent=compared.length+'商品を比べる'
};
const persistUtilities=()=>{
  writeList(SAVED_KEY,saved);writeList(COMPARE_KEY,compared);
  syncUtilityButtons();syncCompareBar();renderSaved();renderCompare()
};
let activeModal=null,modalTrigger=null,modalScroll=0;
const focusable=modal=>Array.from(modal.querySelectorAll('button,a[href],input,select,summary,[tabindex="0"]')).filter(el=>!el.disabled&&el.getClientRects().length);
const closeModal=()=>{
  if(!activeModal)return;
  activeModal.hidden=true;activeModal=null;
  document.body.classList.remove('modal-open');document.body.style.top='';
  document.querySelectorAll('.market-masthead,header,nav,main,footer').forEach(el=>el.inert=false);
  window.scrollTo({top:modalScroll,behavior:'instant'});
  if(modalTrigger?.isConnected)modalTrigger.focus({preventScroll:true});
};
const openModal=modal=>{
  if(!modal)return;
  if(activeModal)closeModal();
  modalTrigger=document.activeElement;modalScroll=window.scrollY;activeModal=modal;
  document.body.style.top=-modalScroll+'px';document.body.classList.add('modal-open');
  // Some dialogs live inside main; keep their ancestor active and trap focus below.
  document.querySelectorAll('.market-masthead,header,nav,main,footer').forEach(el=>el.inert=!el.contains(modal));
  modal.hidden=false;focusable(modal)[0]?.focus({preventScroll:true});
};
document.addEventListener('click',e=>{
  const saveBtn=e.target.closest('[data-save-product]');
  if(saveBtn){
    const item=fromButton(saveBtn),key=itemKey(item),exists=saved.some(x=>itemKey(x)===key);
    saved=exists?saved.filter(x=>itemKey(x)!==key):[item,...saved].slice(0,30);
    persistUtilities();toast(exists?'保存から外しました':'買い物メモに保存しました');
    send('product_save_toggle',{category_id:item.category,product_id:item.id,saved:exists?0:1});return
  }
  const compareBtn=e.target.closest('[data-compare-product]');
  if(compareBtn){
    const item=fromButton(compareBtn),key=itemKey(item),exists=compared.some(x=>itemKey(x)===key);
    if(exists){compared=compared.filter(x=>itemKey(x)!==key);persistUtilities();toast('比較から外しました');return}
    if(compared.length&&compared[0].category!==item.category){toast('比較は同じ食品カテゴリで選んでください');return}
    if(compared.length>=3){toast('比較できるのは3商品までです');return}
    compared.push(item);persistUtilities();toast('比較に追加しました');
    send('product_compare_add',{category_id:item.category,product_id:item.id,compare_count:compared.length});return
  }
  const remove=e.target.closest('[data-remove-saved]');
  if(remove){saved=saved.filter(x=>itemKey(x)!==remove.dataset.removeSaved);persistUtilities();return}
  const removeCompare=e.target.closest('[data-remove-compare]');
  if(removeCompare){compared=compared.filter(x=>itemKey(x)!==removeCompare.dataset.removeCompare);persistUtilities();toast('比較から外しました');document.querySelector(compared.length?'[data-open-compare]':'[data-open-saved]')?.focus({preventScroll:true});return}
  if(e.target.closest('[data-open-saved]')){renderSaved();openModal(document.querySelector('[data-saved-modal]'));return}
  if(e.target.closest('[data-close-saved]')){closeModal();return}
  if(e.target.closest('[data-open-compare]')){renderCompare();openModal(document.querySelector('[data-compare-modal]'));send('product_compare_open',{compare_count:compared.length});return}
  if(e.target.closest('[data-close-compare]')){closeModal();return}
  if(e.target.closest('[data-clear-compare]')){compared=[];persistUtilities();toast('比較をクリアしました');return}
  const modal=e.target.closest('.utility-modal');
  if(modal&&e.target===modal)closeModal()
});
document.addEventListener('keydown',e=>{
  if(!activeModal)return;
  if(e.key==='Escape'){e.preventDefault();closeModal();return}
  if(e.key==='Tab'){
    const controls=focusable(activeModal),first=controls[0],last=controls[controls.length-1];
    if(!first)return;
    if(e.shiftKey&&(document.activeElement===first||!activeModal.contains(document.activeElement))){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&(document.activeElement===last||!activeModal.contains(document.activeElement))){e.preventDefault();first.focus()}
  }
});
persistUtilities();
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
        cta_label, cta_variant = cta_copy(item, "table", rank)
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
            f"""<tr data-bucket="{bucket(item, category['id'])}" data-shopping-bucket="{shopping_bucket(item, category['id'])}" data-search-text="{search_text}" {attrs}>
<td data-cell="rank" data-rank>{rank_html}</td>
<td data-cell="image">{image}</td>
<td data-cell="product">{product_identity_html(item, category)}<div class="shop">{html.escape(item['shop'])}</div><div class="product-badges">{recommendation} {shipping} {promo}</div><div class="trend-row">{price_history_badges(item)}</div>{product_history_details(item)}</td>
<td data-cell="quantity">{html.escape(quantity_text(item, category['id']))}</td>
<td data-cell="price">¥{item['price']:,}</td>
<td data-cell="unit"><div class="unit">{yen(primary)}</div><div class="unit-label">{html.escape(category['primary_label'])}</div>{secondary}</td>
<td data-cell="cta">{product_action_buttons(item, category, primary)}<a class="cta" href="{html.escape(item['url'], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
 data-affiliate="rakuten" data-category="{category['id']}" data-product-id="{html.escape(item['id'], quote=True)}"
 data-product-name="{html.escape(item['name'], quote=True)}" data-rank="{rank}" data-metric="{primary_metric}"
 data-unit-price="{primary:.6f}" data-shipping="{item['shipping_status']}" {cta_attrs(cta_variant)}>{html.escape(cta_label)}</a></td>
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

    content = f"""<section class="comparison-inner" data-comparison data-start-rank="{start_rank}">
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
<p class="sub" data-intent-note></p><div class="empty-filter" data-empty-filter>条件に合う商品がありません。検索語や容量条件を変えてください。</div>
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
    elif mode == "pack_count_24":
        picked = [x for x in items if int(x["quantity"].get("count") or 0) == 24]
    elif mode == "pack_count_40plus":
        picked = [x for x in items if int(x["quantity"].get("count") or 0) >= 40]
    elif mode == "water_500_24":
        picked = [x for x in items if 450 <= float(x["quantity"].get("unit_volume_ml") or 0) <= 600 and int(x["quantity"].get("count") or 0) == 24]
    elif mode == "water_500_48":
        picked = [x for x in items if 450 <= float(x["quantity"].get("unit_volume_ml") or 0) <= 600 and int(x["quantity"].get("count") or 0) == 48]
    elif mode == "water_1l":
        picked = [x for x in items if 900 <= float(x["quantity"].get("unit_volume_ml") or 0) <= 1100]
    elif mode == "rice_musenmai":
        picked = [x for x in items if "無洗米" in x["name"]]
    elif mode == "oats_rolled":
        picked = [x for x in items if re.search(r"ロールド\s*オーツ|ロールドオーツ", x["name"], re.I)]
    elif mode == "oats_quick":
        picked = [x for x in items if re.search(r"クイック\s*オーツ|クイックオーツ", x["name"], re.I)]
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


def eligible_auto_guides(results: dict, min_items: int = 3) -> list[dict]:
    category_by_id = {category["id"]: category for category in CATEGORIES}
    eligible = []
    for spec in AUTO_GUIDE_RULES:
        category = category_by_id[spec["category_id"]]
        included, _ = results.get(category["id"], ([], []))
        matched = guide_filter_items(spec, included, category)
        if len(matched) >= min_items:
            enriched = dict(spec)
            enriched["matched_count"] = len(matched)
            eligible.append(enriched)
    return eligible


def optimization_report(results: dict, auto_guides: list[dict], updated: datetime) -> dict:
    category_rows = {}
    total_included = 0
    history_ready = 0
    low_inventory = []
    for category in CATEGORIES:
        included, other = results.get(category["id"], ([], []))
        total_included += len(included)
        ready = sum(
            1 for item in included
            if int((item.get("price_history") or {}).get("observed_days") or 0) >= 2
        )
        history_ready += ready
        category_rows[category["id"]] = {
            "name": category["name"],
            "included_count": len(included),
            "shipping_unknown_count": len(other),
            "history_ready_count": ready,
            "history_ready_rate": round(ready / len(included), 4) if included else 0,
        }
        if len(included) < 15:
            low_inventory.append(category["id"])

    deals, _ = deal_entries(results)
    history_rate = round(history_ready / total_included, 4) if total_included else 0
    priorities = []
    if low_inventory:
        priorities.append({
            "type": "product_coverage",
            "priority": 1,
            "categories": low_inventory,
            "action": "安全な掲載候補を増やす検索・解析改善を優先",
        })
    if history_rate < 0.8:
        priorities.append({
            "type": "price_history",
            "priority": 2,
            "coverage": history_rate,
            "action": "自動更新を継続し価格履歴の母数を増やす",
        })
    priorities.append({
        "type": "cta_measurement",
        "priority": 3,
        "action": "GA4でcta_variant×click_positionのaffiliate_clickを比較",
    })
    priorities.append({
        "type": "search_console",
        "priority": 4,
        "action": "Search Console接続時に自動SEOページの表示回数・CTR・順位を取り込み評価",
    })
    return {
        "generated_at": updated.isoformat(),
        "site_id": SITE_ID,
        "inventory": category_rows,
        "price_history": {
            "ready_count": history_ready,
            "included_count": total_included,
            "ready_rate": history_rate,
            "deal_count": len(deals),
        },
        "auto_seo": {
            "minimum_products": 3,
            "published_count": len(auto_guides),
            "pages": [
                {
                    "slug": spec["slug"],
                    "category_id": spec["category_id"],
                    "matched_count": spec.get("matched_count", 0),
                    "title": spec["title"],
                }
                for spec in auto_guides
            ],
        },
        "analytics": {
            "ga4_configured": bool(GA_ID),
            "affiliate_event": "affiliate_click",
            "dimensions": [
                "click_position",
                "cta_variant",
                "category_id",
                "rank",
                "comparison_metric",
                "page_path",
            ],
            "search_console_build_ingestion": False,
        },
        "priority_queue": priorities,
    }



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
    cards = top3_html(picked, category) if picked else f"""<section class="section explain">
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
{service_shortcuts_html()}
<main class="wrap">
<section class="section explain"><h2>このページの見方</h2>
<p>{html.escape(spec['intro'])}</p>
<p class="fine">商品名・容量・セット数を安全に読み取れない候補は除外し、クーポンやポイントは通常単価へ自動反映しません。</p>
</section>
{cards}
{more}
{faq_html(faqs)}
<section class="section explain"><h2>もっと広く比較する</h2><p><a class="finder-go" href="../../categories/{category['id']}/">{html.escape(category['name'])}の全ランキングを見る →</a></p></section>
{utility_panels_html()}
</main><script>{JS}</script>
<footer><div class="wrap">当サイトは楽天アフィリエイトを利用しています。価格は取得時点の参考情報です。</div></footer>
</body></html>"""



def saved_watch_page(updated: datetime) -> str:
    head = page_head(
        "買い物メモ｜食品コスパ比較",
        "ブラウザに保存した食品だけを、最新価格・値下がり・30日最安・価格履歴で確認します。",
        f"{SITE_URL}saved/",
    ).replace(
        '<meta name="robots" content="index,follow">',
        '<meta name="robots" content="noindex,nofollow">',
    )
    body = f"""<header><div class="wrap hero-layout">
<div><a class="brand" href="../">食品コスパ比較</a><div class="eyebrow">MY WATCH</div>
<h1>保存した商品の<br>値下がりだけ追う。</h1>
<p class="lead">「あとで見る」に入れた商品を、最新の楽天取得データと照合して確認します。</p>
<div class="hero-tags"><span class="hero-tag">現在価格</span><span class="hero-tag">前回比</span><span class="hero-tag">30日最安</span></div>
<p class="note">サイト最終更新: {updated:%Y-%m-%d %H:%M} JST</p></div>
<div class="category-hero-art">{guide_mascot()}</div></div></header>
{service_shortcuts_html()}
<main class="wrap">
<section class="section saved-dashboard">
<div class="section-kicker">SAVED PRICE WATCH</div><h2>買い物メモ</h2>
<div class="saved-watch-summary">
<div><span>保存中</span><strong data-watch-total>0</strong></div>
<div><span>値下がり</span><strong data-watch-drops>0</strong></div>
<div><span>30日最安</span><strong data-watch-lows>0</strong></div>
</div>
<div class="saved-watch-tabs">
<button type="button" class="selected" data-watch-filter="all">すべて</button>
<button type="button" data-watch-filter="drop">値下がり</button>
<button type="button" data-watch-filter="low">30日最安</button>
</div>
<div data-watch-status class="saved-watch-status">最新データを確認しています…</div>
<div data-watch-list class="saved-watch-list"></div>
</section>
<section class="section explain">
<h2>この画面について</h2>
<p>保存内容はこのブラウザ内だけに残ります。価格判定は未来予測ではなく、当サイトが取得した実測履歴との比較です。</p>
<p><a class="finder-go" href="../">食品を探しに戻る →</a></p>
</section>
</main>"""
    script = r"""<script>
(()=>{
const KEY='food_cost_saved_v1';
const CATEGORY_META={
  'pack-rice':{name:'パックご飯',metric:'per_serving',unit:'1食あたり'},
  'rice':{name:'米',metric:'per_kg',unit:'1kgあたり'},
  'carbonated-water':{name:'炭酸水',metric:'per_liter',unit:'1Lあたり'},
  'oatmeal':{name:'オートミール',metric:'per_100g',unit:'100gあたり'}
};
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const money=n=>'¥'+Number(n||0).toLocaleString('ja-JP',{maximumFractionDigits:1});
const compact=s=>{s=String(s||'').replace(/[【】\[\]〈〉《》]/g,' ').replace(/\s*[｜|／/]\s*/g,' ').replace(/\s+/g,' ').trim();return s.length>64?s.slice(0,63)+'…':s};
const readSaved=()=>{try{const v=JSON.parse(localStorage.getItem(KEY)||'[]');return Array.isArray(v)?v:[]}catch(e){return[]}};
let saved=readSaved(), rows=[], active='all';
const status=document.querySelector('[data-watch-status]'),list=document.querySelector('[data-watch-list]');
const total=document.querySelector('[data-watch-total]'),drops=document.querySelector('[data-watch-drops]'),lows=document.querySelector('[data-watch-lows]');
const signal=item=>{
  const h=item&&item.price_history||{}, series=h.series_30d||[];
  if(Number(h.observed_days||0)<2)return ['履歴蓄積中','neutral'];
  if(h.is_30d_low&&Number(h.price_delta)<0)return ['買い時寄り','buy'];
  if(Number(h.price_delta)<0)return ['買い時寄り','buy'];
  const current=series.length?Number(series[series.length-1].unit):0, low=Number(h.lowest_30d_unit||0);
  if(low&&current>low*1.05)return ['様子見寄り','wait'];
  return ['相場圏','neutral'];
};
const chart=item=>{
  const series=item&&item.price_history&&item.price_history.series_30d||[];
  const vals=series.map(p=>Number(p.unit)).filter(Number.isFinite);
  if(vals.length<2)return '<div class="sparkline-empty">次回取得後からグラフを表示</div>';
  const w=220,h=76,p=8,lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo;
  const pts=vals.map((v,i)=>{const x=p+(w-p*2)*i/Math.max(1,vals.length-1);const y=span<1e-9?h/2:p+(h-p*2)*(hi-v)/span;return x.toFixed(1)+','+y.toFixed(1)}).join(' ');
  const tone=signal(item)[1];
  return '<svg class="saved-chart sparkline '+tone+'" viewBox="0 0 220 76" role="img" aria-label="30日価格推移"><line x1="8" y1="68" x2="212" y2="68" class="spark-grid"/><polyline points="'+pts+'" fill="none" vector-effect="non-scaling-stroke"/></svg>';
};
const render=()=>{
  total.textContent=saved.length;
  drops.textContent=rows.filter(r=>r.live&&Number(r.live.price_history&&r.live.price_history.price_delta)<0).length;
  lows.textContent=rows.filter(r=>r.live&&r.live.price_history&&r.live.price_history.is_30d_low).length;
  let view=rows.filter(r=>{
    if(active==='drop')return r.live&&Number(r.live.price_history&&r.live.price_history.price_delta)<0;
    if(active==='low')return r.live&&r.live.price_history&&r.live.price_history.is_30d_low;
    return true;
  });
  view.sort((a,b)=>{
    const ad=a.live&&Number(a.live.price_history&&a.live.price_history.price_delta)||0;
    const bd=b.live&&Number(b.live.price_history&&b.live.price_history.price_delta)||0;
    return ad-bd;
  });
  if(!view.length){list.innerHTML='<div class="utility-empty">'+(saved.length?'この条件の商品はありません。':'まだ保存した商品がありません。')+'</div>';return}
  list.innerHTML=view.map(r=>{
    const s=r.saved,l=r.live,meta=CATEGORY_META[s.category]||{name:s.categoryName||'',metric:'',unit:s.unitLabel||''};
    if(!l)return '<article class="watch-card unavailable"><div><span class="tag warn">現在の掲載外</span><h3>'+esc(compact(s.name))+'</h3><p>'+esc(meta.name)+' ・ 保存時 '+money(s.price)+'</p></div><button data-watch-remove="'+esc(s.category+'|'+s.id)+'">保存から削除</button></article>';
    const h=l.price_history||{}, metric=meta.metric, unit=Number(l.unit_prices&&l.unit_prices[metric]||0), sig=signal(l);
    const prev=h.previous_price==null?'—':money(h.previous_price);
    const low=h.lowest_30d_unit==null?'—':money(h.lowest_30d_unit);
    const drop=Number(h.price_delta)<0?'<span class="trend-badge drop">↓ '+money(Math.abs(Number(h.price_delta)))+' 前回比</span>':'';
    const lowBadge=h.is_30d_low?'<span class="trend-badge low">30日最安</span>':'';
    return '<article class="watch-card"><div class="watch-media">'+(l.image?'<img src="'+esc(l.image)+'" alt="">':'')+'</div><div class="watch-copy">'+
      '<div class="watch-top"><span>'+esc(meta.name)+'</span><div>'+drop+lowBadge+'</div></div>'+
      '<h3 title="'+esc(l.name)+'">'+esc(compact(l.name))+'</h3>'+
      '<div class="watch-price"><strong>'+money(l.price)+'</strong><span>'+money(unit)+' '+esc(meta.unit)+'</span></div>'+
      '<div class="watch-history-stats"><div><span>前回価格</span><b>'+prev+'</b></div><div><span>30日最安単価</span><b>'+low+'</b></div><div><span>取得回数</span><b>'+Number(h.observed_days||0)+'回</b></div></div>'+
      chart(l)+'<div class="buy-signal '+sig[1]+'"><span>'+sig[0]+'</span></div>'+
      '<div class="watch-actions"><a class="cta" href="'+esc(l.url)+'" target="_blank" rel="nofollow sponsored noopener">楽天で確認 →</a><button data-watch-remove="'+esc(s.category+'|'+s.id)+'">保存から削除</button></div></div></article>'
  }).join('');
};
document.querySelectorAll('[data-watch-filter]').forEach(btn=>btn.addEventListener('click',()=>{active=btn.dataset.watchFilter;document.querySelectorAll('[data-watch-filter]').forEach(x=>x.classList.toggle('selected',x===btn));render()}));
document.addEventListener('click',e=>{const b=e.target.closest('[data-watch-remove]');if(!b)return;const key=b.dataset.watchRemove;saved=saved.filter(x=>x.category+'|'+x.id!==key);localStorage.setItem(KEY,JSON.stringify(saved));rows=rows.filter(r=>r.saved.category+'|'+r.saved.id!==key);render()});
if(!saved.length){status.textContent='「あとで見る」に商品を追加すると、ここで価格を追えます。';render();return}
fetch('../data/products.json',{cache:'no-store'}).then(r=>r.json()).then(data=>{
  const live=new Map();
  Object.entries(data.categories||{}).forEach(([cat,payload])=>[...(payload.included||[]),...(payload.shipping_unknown||[])].forEach(item=>live.set(cat+'|'+item.id,item)));
  rows=saved.map(s=>({saved:s,live:live.get(s.category+'|'+s.id)||null}));
  status.textContent='最新の取得データと照合しました。';render();
}).catch(()=>{rows=saved.map(s=>({saved:s,live:null}));status.textContent='最新データを取得できませんでした。保存内容のみ表示します。';render()});
})();
</script>"""
    return head + body + script + """<footer><div class="wrap">保存データはこのブラウザ内に保持されます。</div></footer></body></html>"""




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
</head><body>
<div class="market-masthead"><div class="wrap"><a class="market-logo" href="{SITE_URL}"><b>Food Cost<em>EVERYDAY MARCHÉ</em></b><span>食品コスパ比較</span></a><small>GOOD FOOD. SMART CHOICES.</small></div></div>"""


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
<div><h2>{html.escape(category['name'])}を比べるコツ</h2>
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
<a href="../../deals/">今日のお買い得</a>
<a href="../../saved/">買い物メモ</a>
<a href="../../">トップ</a>
</div></nav>
<main class="wrap">"""
    )
    parts.append(category_summary(category, included, other))
    parts.append(shopping_journey_html())
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
        f"""<section class="section explain">
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


def guide_links_html(specs: list[dict] | None = None) -> str:
    specs = specs or GUIDE_SPECS
    links = "".join(
        f"""<a class="intent-card" href="guides/{spec['slug']}/">
<span>{html.escape(spec['title'])}</span><small>{html.escape(spec['intro'])}</small><b>比較を見る →</b>
</a>"""
        for spec in specs
    )
    return f"""<section class="section intent-section">
<div class="section-kicker">POPULAR SEARCHES</div>
<h2>よく比べられる条件から探す。</h2>
<div class="intent-grid">{links}</div>
</section>"""



def home_page(results: dict, updated: datetime, guide_specs: list[dict] | None = None) -> str:
    parts = [
        page_head(
            "食品コスパ比較｜容量・数量・送料をそろえて単価比較",
            "米、パックご飯、炭酸水、オートミールを1kg・1L・1食・100gあたりへ換算し、送料条件を分けて比較します。",
            SITE_URL,
        )
    ]
    parts.append(
        f"""<header class="home-hero"><div class="wrap hero-layout">
<div class="hero-copy">
<div class="eyebrow">毎日の食品を、賢く選ぶ小さなマルシェ</div>
<span class="brand">Welcome to your everyday marché.</span>
<h1>今日の買い物を、<br>ちょっと楽しく。<br>ちょっと賢く。</h1>
<p class="lead">いつものご飯も、朝の一杯も。<br>単価と送料をそろえて、わが家にちょうどいいものを。</p>
<div class="hero-actions"><a class="cta" href="#quick-finder" data-hero-primary data-start-route="finder">今日の買い物をはじめる →</a></div><div class="hero-subroutes"><a href="#today-market">今日のお買い得を見る</a><a href="#quick-finder" data-hero-known>買うものが決まっている</a></div>
<p class="note">最終価格確認: {updated:%Y-%m-%d %H:%M} JST</p>
</div>
{hero_visual()}
</div></header>
{service_shortcuts_html()}
<main class="wrap">
{choice_finder_html(results)}
{today_market_html(results)}
{discovery_shelves_html(results)}
<section class="section" id="categories">
<div class="section-kicker">THE MARKET AISLES</div>
<h2>売り場から探す。</h2><p class="sub">買うものが決まっているときは、こちらから。</p>
<section class="grid">"""
    )
    last_aisle = None
    for category in CATEGORIES:
        aisle = {"pack-rice":"ごはん・お米", "rice":"ごはん・お米", "carbonated-water":"飲みもの", "oatmeal":"朝食・穀物"}.get(category["id"],"その他の売り場")
        if aisle != last_aisle:
            parts.append(f'<h3 class="aisle-group">{aisle}</h3>')
            last_aisle = aisle
        included, _ = results[category["id"]]
        best = included[0]["unit_prices"][category["primary"]] if included else None
        message = (
            f"取得商品では {category['primary_label']} {yen(best)}〜"
            if best is not None else "比較データを準備中"
        )
        parts.append(
            f"""<a class="card category-card {category['id']}" href="categories/{category['id']}/" data-start-route="categories">
<div class="category-art">{category_illustration(category["id"], True)}</div>
<div class="category-copy">
<span class="aisle-name">{html.escape({"pack-rice":"READY TO EAT", "rice":"RICE & GRAINS", "carbonated-water":"DRINKS", "oatmeal":"BREAKFAST"}.get(category["id"], "MARKET AISLE"))}</span><div class="category-name">{category['name']}</div>
<div class="category-price">{html.escape(message.replace('取得商品では ', ''))}</div>
<div class="category-meta">送料込み {len(included)}件を比較中</div>
<p>{html.escape(category['intro'])}</p>
<span class="category-go">この売り場へ →</span>
</div>
</a>"""
        )
    parts.append(
        """</section></section>"""
    )
    parts.append(shopping_journey_html())
    parts.append(guide_links_html(guide_specs))
    parts.append(comparison_flow_html())
    parts.append(
        f"""<section class="section explain">
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
    import shutil
    shutil.copytree(Path(__file__).parents[1] / "assets", OUT / "assets", dirs_exist_ok=True)
    updated = datetime.now(ZoneInfo("Asia/Tokyo"))
    history = load_price_history(HISTORY_SOURCE)
    results = {}
    export = {"generated_at": updated.isoformat(), "categories": {}}

    for category in CATEGORIES:
        included, other, audit = collect(category)
        apply_price_history(history, category, included + other, updated.date())
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
    auto_guides = eligible_auto_guides(results)
    all_guides = GUIDE_SPECS + auto_guides
    for spec in all_guides:
        category = category_by_id[spec["category_id"]]
        included, _ = results[category["id"]]
        target = OUT / "guides" / spec["slug"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(
            guide_page(spec, category, included, updated),
            encoding="utf-8",
        )

    deals_target = OUT / "deals"
    deals_target.mkdir(parents=True, exist_ok=True)
    (deals_target / "index.html").write_text(
        deals_page(results, updated),
        encoding="utf-8",
    )

    saved_target = OUT / "saved"
    saved_target.mkdir(parents=True, exist_ok=True)
    (saved_target / "index.html").write_text(
        saved_watch_page(updated),
        encoding="utf-8",
    )

    (OUT / "index.html").write_text(home_page(results, updated, all_guides), encoding="utf-8")
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "products.json").write_text(
        json.dumps(export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_price_history(history, OUT / "data" / "price-history.json")
    (OUT / "data" / "optimization-report.json").write_text(
        json.dumps(optimization_report(results, auto_guides, updated), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )

    urls = [SITE_URL, f"{SITE_URL}deals/"] + [
        f"{SITE_URL}categories/{category['id']}/"
        for category in CATEGORIES
    ] + [
        f"{SITE_URL}guides/{spec['slug']}/"
        for spec in all_guides
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
