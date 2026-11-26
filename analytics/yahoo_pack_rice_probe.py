"""Read-only candidate discovery. No publication, affiliate redirects or price claims."""
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener

API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
# JAN is a search seed, not a claim that each Rakuten listing carries that JAN.
# Ito-Yokado: https://iyec.itoyokado.co.jp/shop/g/g4562403572691/
# Matsukiyo: https://www.matsukiyococokara-online.com/store/catalog/product/view/id/4973360566850
PRODUCTS = (
    ("iris-180g-24", "4562403572691", 180, 24,
     r"アイリス", r"低温製法米", r"180\s*g\s*[×x*]\s*24\s*(?:食|パック|個|p)"),
    ("sato-ginshari-200g-80", "4973360566850", 200, 80,
     r"サトウ", r"銀シャリ", r"200\s*g\s*[×x*]\s*5\s*(?:食|個)?\s*\)?\s*[×x*]\s*16\s*(?:袋|パック|個)"),
)
EXCLUDE = r"訳あり|賞味期限間近|お試し|詰め合わせ|選べる|玄米|もち麦|雑穀|定期購入|ふるさと納税"

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
              "note": "Candidate counts only; no confirmed product matches, checkout totals or affiliate links.",
              "products": {}}
    if not key:
        result["status"] = "NOT_CONFIGURED"
        return result
    rows = catalog["categories"]["pack-rice"]["included"]
    for index, product in enumerate(PRODUCTS):
        if index:
            time.sleep(2.5)
        try:
            counts = summarize(request(product[1], key), product)
            counts["rakuten_title_quantity_candidates"] = rakuten_candidates(rows, product)
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
