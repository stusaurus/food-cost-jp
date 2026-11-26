"""Read-only candidate discovery. No publication, affiliate redirects or price claims."""
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import HTTPRedirectHandler, build_opener

API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
# JAN is a search seed, not a claim that each Rakuten listing carries that JAN.
# Ito-Yokado: https://iyec.itoyokado.co.jp/shop/g/g4562403572691/
# Matsukiyo: https://www.matsukiyococokara-online.com/store/catalog/product/view/id/4973360566850
PRODUCTS = (
    ("iris-180g-24", "4562403572691", 180, 24,
     r"アイリス", r"低温製法米", r"180\s*g\s*(?:[×x*]\s*|\(?\s*1\s*ケース\s*)24\s*(?:食|パック|個|p)(?!\d)"),
    ("sato-ginshari-200g-80", "4973360566850", 200, 80,
     r"サトウ", r"銀シャリ", r"200\s*g\s*[×x*]\s*5\s*(?:食|個)?\s*\)?\s*[×x*]\s*16\s*(?:袋|パック|個)"),
)
EXCLUDE = r"訳あり|賞味期限間近|お試し|詰め合わせ|選べる|玄米|もち麦|雑穀|定期購入|ふるさと納税|大盛り|小盛り|糖質オフ"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def normalize(name):
    return unicodedata.normalize("NFKC", name).lower() if isinstance(name, str) else ""

def title_candidate(name, product):
    name = normalize(name)
    return bool(not re.search(EXCLUDE, name) and all(re.search(pattern, name) for pattern in product[4:]))

def rakuten_candidates(rows, product):
    return sum(title_candidate(row.get("name"), product)
               and row.get("shipping_status") == "included"
               and row.get("quantity", {}).get("unit_weight_g") == product[2]
               and row.get("quantity", {}).get("count") == product[3]
               for row in rows)

# Independently checked merchant listing paths, not generic title similarity.
# https://www.satosyokuhin.co.jp/products/products_rice_163.html
# https://store.shopping.yahoo.co.jp/likaman/950871-16.html
SATO_RAKUTEN_ID = "likaman:10040020"
SATO_RAKUTEN_PATH = "/likaman/950871-16/"
SATO_YAHOO_CODE = "likaman_950871-16"

def exact_sato_rakuten(rows, product):
    for row in rows:
        if row.get("id") != SATO_RAKUTEN_ID or not rakuten_candidates([row], product):
            continue
        try:
            url = urlsplit(row["url"])
            targets = parse_qs(url.query).get("pc", [])
            if url.scheme != "https" or url.hostname != "hb.afl.rakuten.co.jp" or len(targets) != 1:
                continue
            target = urlsplit(targets[0])
            q = row["quantity"]
            if (target.scheme == "https" and target.netloc == "item.rakuten.co.jp"
                    and target.path == SATO_RAKUTEN_PATH
                    and q.get("component_counts") == [5, 16]
                    and q.get("total_weight_g") == 16000
                    and row.get("postage_included") is True
                    and type(row.get("price")) is int and row["price"] > 0):
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False

def exact_sato_yahoo(hits, product):
    # Match the verified merchant SKU and product URL without visiting it.
    for hit in hits:
        if (hit.get("code") != SATO_YAHOO_CODE or hit.get("janCode") != product[1]
                or hit.get("inStock") is not True or not title_candidate(hit.get("name"), product)
                or not isinstance(hit.get("shipping"), dict) or hit["shipping"].get("code") != 2
                or type(hit.get("price")) is not int or hit["price"] <= 0):
            continue
        try:
            target = urlsplit(hit["url"])
            if (target.scheme == "https" and target.netloc == "store.shopping.yahoo.co.jp"
                    and target.path == "/likaman/950871-16.html"):
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False

SHIPPING_CONDITIONS = re.compile(
    r"条件付き送料無料|送料無料ライン|送料別(?:途)?|送料有料|配送不可|"
    r"(?:北海道|沖縄|離島|一部地域).{0,24}(?:送料|別途|対象外|除く|追加料金|追加費用|加算|配送できません)|"
    r"(?:送料|配送|発送).{0,24}(?:北海道|沖縄|離島|一部地域)|"
    r"[\d,.]+円(?:\(税込\))?(?:以上|から).{0,20}(?:送料無料|送料0円)|"
    r"(?:送料無料|送料0円).{0,20}[\d,.]+円(?:\(税込\))?(?:以上|から)"
)

def price_pair_preview(rows, hits, product, checked_at, now=None):
    """Internal diagnostic only. Never equate shipping flags with final checkout."""
    now = now or datetime.now(timezone.utc)
    result = {"status": "NOT_COMPARABLE", "reason": "IDENTITY_OR_PRICE_UNVERIFIED"}
    try:
        stamp = datetime.fromisoformat(checked_at)
        if stamp.tzinfo is None or not timedelta(hours=-1) <= now - stamp <= timedelta(hours=48):
            return dict(result, reason="STALE_OR_INVALID_RAKUTEN_TIMESTAMP")
    except (TypeError, ValueError):
        return dict(result, reason="STALE_OR_INVALID_RAKUTEN_TIMESTAMP")
    r = [row for row in rows if exact_sato_rakuten([row], product)]
    y = [hit for hit in hits if exact_sato_yahoo([hit], product)]
    if len(r) != 1 or len(y) != 1:
        return result
    r, y = r[0], y[0]
    label = y.get("priceLabel")
    if y.get("condition") != "new" or not isinstance(label, dict) or label.get("taxable") is not True:
        return dict(result, reason="NEW_OR_TAX_INCLUSIVE_UNVERIFIED")
    terms = " ".join(normalize(y.get(k)) for k in ("name", "headLine", "description", "shipping"))
    # Include explicit shipping-label name; don't rely on the numeric code alone.
    terms += " " + normalize(y["shipping"].get("name"))
    terms += " " + normalize(r.get("raw_name")) + " " + normalize(r.get("name"))
    if SHIPPING_CONDITIONS.search(terms):
        return dict(result, reason="SHIPPING_CONDITIONS_REQUIRE_REVIEW")
    return {"status": "API_PRICE_PREVIEW_ONLY", "rakuten_listed_price_yen": r["price"],
            "yahoo_listed_price_yen": y["price"],
            "listed_price_difference_yen": abs(r["price"] - y["price"]),
            "rakuten_checked_at": checked_at, "yahoo_checked_at": now.isoformat(),
            "pack_count": product[3], "unit_weight_g": product[2],
            "rakuten_per_serving_yen": round(r["price"] / product[3], 2),
            "yahoo_per_serving_yen": round(y["price"] / product[3], 2),
            "checkout_total_verified": False, "publish_allowed": False}

def summarize(hits, product):
    if not isinstance(hits, list) or any(not isinstance(hit, dict) for hit in hits):
        raise ValueError("response schema")
    unique = {}
    for hit in hits:
        code = hit.get("code")
        if isinstance(code, str) and code:
            unique.setdefault(code, hit)
    jan = [h for h in unique.values() if h.get("janCode") == product[1]]
    title = [h for h in jan if title_candidate(h.get("name"), product)
             and h.get("inStock") is True]
    free = [h for h in title if isinstance(h.get("shipping"), dict)
            and h["shipping"].get("code") == 2]
    return {"api_hits": len(unique), "jan_hits": len(jan),
            "title_quantity_candidates": len(title), "free_shipping_flag_candidates": len(free)}

def fetch(jan, key):
    query = urlencode({"appid": key, "jan_code": jan, "in_stock": "true",
                       "condition": "new", "results": 50})
    with build_opener(NoRedirect()).open(API + "?" + query, timeout=20) as response:
        return json.loads(response.read(3_000_000))["hits"]

def report(catalog, key, request=fetch):
    result = {"scope": "food-cost-jp/pack-rice", "status": "OK",
              "note": "Read-only identity diagnostics; no checkout totals or affiliate links published. Merchant SKU evidence is not final shipping or ad approval.",
              "products": {}}
    if not key:
        result["status"] = "NOT_CONFIGURED"
        return result
    rows = catalog["categories"]["pack-rice"]["included"]
    for index, product in enumerate(PRODUCTS):
        if index:
            time.sleep(2.5)
        try:
            hits = request(product[1], key)
            counts = summarize(hits, product)
            counts["rakuten_title_quantity_candidates"] = rakuten_candidates(rows, product)
            if product[0] == "sato-ginshari-200g-80":
                counts["verified_rakuten_merchant_sku"] = exact_sato_rakuten(rows, product)
                counts["verified_yahoo_merchant_sku"] = exact_sato_yahoo(hits, product)
                counts["both_merchant_skus_verified"] = counts["verified_rakuten_merchant_sku"] and counts["verified_yahoo_merchant_sku"]
                counts["price_preview"] = price_pair_preview(rows, hits, product, catalog.get("generated_at"))
            result["products"][product[0]] = counts
        except HTTPError as exc:
            result["products"][product[0]] = {"status": "UNAVAILABLE", "reason": "HTTP_" + str(exc.code)}
            result["status"] = "PARTIAL_OR_UNAVAILABLE"
        except Exception:
            result["products"][product[0]] = {"status": "UNAVAILABLE", "reason": "READ_OR_SCHEMA_FAILED"}
            result["status"] = "PARTIAL_OR_UNAVAILABLE"
    return result

if __name__ == "__main__":
    catalog = json.loads(Path("data/products.json").read_text(encoding="utf-8"))
    result = report(catalog, os.getenv("YAHOO_APP_ID", "").strip())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "OK" else 1)
