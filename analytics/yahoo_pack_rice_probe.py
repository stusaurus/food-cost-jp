"""Read-only candidate discovery. No publication, affiliate redirects or price claims."""
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, parse_qs, unquote, urlunsplit
from urllib.request import HTTPRedirectHandler, build_opener

VC_HOST = "ck.jp.ap.valuecommerce.com"

class YahooUnavailable(Exception):
    pass

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

def safe_url(value):
    if not isinstance(value, str) or re.search(r'[\x00-\x20\x7f<>"\\]', value):
        return None
    try:
        url = urlsplit(value)
        if url.netloc != url.hostname or url.fragment:
            return None
    except ValueError:
        return None
    return url


def affiliate_config(value):
    """Accept the extracted referral URL or the URL-encoded form in the docs."""
    raw = unquote(value.strip())
    url = safe_url(raw)
    params = parse_qs(url.query, keep_blank_values=True) if url else {}
    if (not url or url.scheme not in ("http", "https") or url.hostname != VC_HOST
            or url.path != "/servlet/referral" or set(params) - {"sid", "pid", "vc_url"}
            or not all(len(params.get(k, [])) == 1 and re.fullmatch(r"[0-9]+", params[k][0])
                       for k in ("sid", "pid"))
            or params.get("vc_url", [""]) != [""]):
        raise YahooUnavailable("affiliate_config_format")
    query = urlencode({"sid": params["sid"][0], "pid": params["pid"][0], "vc_url": ""})
    return urlunsplit(url._replace(query=query)), params["sid"][0], params["pid"][0]


def product_target(value, code):
    url = safe_url(value)
    if not url or url.scheme != "https" or not isinstance(code, str):
        return False
    if url.hostname == "store.shopping.yahoo.co.jp":
        match = re.fullmatch(r"/([\w-]+)/([\w.-]+)\.html", url.path, re.ASCII)
        return bool(match and f"{match[1]}_{match[2]}" == code)
    if url.hostname == "lohaco.yahoo.co.jp":
        match = re.fullmatch(r"/store/h-lohaco/item/([\w-]+)/?", url.path, re.ASCII | re.I)
        return bool(match and code.lower() in {f"{store}_{match[1].lower()}"
                                              for store in ("h-lohaco", "rd-lohaco")})
    return False


def affiliate_target(hit, app_id, sid, pid):
    """Validate the returned ad URL without opening or logging it."""
    value = hit.get("url")
    url = safe_url(value)
    if (not url or url.scheme not in ("https", "http") or url.hostname != VC_HOST
            or url.path != "/servlet/referral"):
        return None
    params = parse_qs(url.query, keep_blank_values=True)
    targets = params.get("vc_url", [])
    if (params.get("sid") != [sid] or params.get("pid") != [pid]
            or len(targets) != 1 or not product_target(targets[0], hit.get("code"))
            or app_id in unquote(value)):
        return None
    return targets[0]

def affiliate_probe(app_id, affiliate_id, request=None):
    """Read-only food-specific ad URL validation. Never output URL or ID."""
    if not affiliate_id:
        return {"status": "NOT_CONFIGURED", "publish_allowed": False}
    if not app_id:
        return {"status": "NOT_CONFIGURED", "publish_allowed": False}
    try:
        prefix, sid, pid = affiliate_config(affiliate_id)
        product = PRODUCTS[1]
        hits = (request or fetch)(product[1], app_id, affiliate_prefix=prefix)
        if not isinstance(hits, list) or any(not isinstance(h, dict) for h in hits):
            raise YahooUnavailable("response_schema")
        verified = 0
        for hit in hits:
            if hit.get("code") != SATO_YAHOO_CODE:
                continue
            target = affiliate_target(hit, app_id, sid, pid)
            if target and exact_sato_yahoo([dict(hit, url=target)], product):
                verified += 1
        return {"status": "VERIFIED" if verified == 1 else "NOT_VERIFIED",
                "verified_food_ad_links": verified, "publish_allowed": False}
    except YahooUnavailable:
        return {"status": "NOT_VERIFIED", "reason": "CONFIG_OR_SCHEMA_INVALID", "publish_allowed": False}
    except Exception:
        return {"status": "UNAVAILABLE", "reason": "REQUEST_FAILED", "publish_allowed": False}

def fetch(jan, key, affiliate_prefix=None, query=None):
    params = {"appid": key, "in_stock": "true", "condition": "new", "results": 50}
    params.update({"jan_code": jan} if jan else {"query": query})
    if affiliate_prefix:
        params.update(affiliate_type="vc", affiliate_id=affiliate_prefix)
    query = urlencode(params)
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

# Merchant listing evidence: same named product and package, not yet a JAN match.
# Yahoo: https://store.shopping.yahoo.co.jp/likaman/927807-24.html
# Yahoo: https://store.shopping.yahoo.co.jp/cocodecow/y388eb.html
EXPANSION = (
    ("pasta", "likaman:10033183", "/likaman/927807-24/", "likaman_927807-24",
     "ディチェコ No.12 500g 24袋", r"ディ[・ ]?チェコ", r"no\.?\s*12(?!\d)",
     r"500\s*g\s*[×x*]?\s*24\s*(?:袋|個)", "unit_weight_g", 500, "total_weight_g", 12000, 24),
    ("mineral-water", "cocodecow:10778153", "/cocodecow/r820gf/", "cocodecow_y388eb",
     "ハルナウォーター 安曇野の自然が育んだ天然水 2L 12本", r"ハルナウォーター", r"安曇野の自然が育んだ天然水",
     r"2\s*l\s*[×x*]?\s*12\s*本", "unit_volume_ml", 2000, "total_volume_ml", 24000, 12),
)

def expansion_title(name, spec):
    n = normalize(name)
    return bool(n and not re.search(EXCLUDE + r"|選択|セット内容変更|予約|配送不可", n)
                and all(re.search(p, n) for p in spec[5:8]))

# Independently reviewed exact retailer listing paths. The water JAN is a
# Yahoo-side identifier corroborated by another retailer; Rakuten JAN is not asserted.
# https://item.rakuten.co.jp/likaman/927807-24/
# https://store.shopping.yahoo.co.jp/likaman/927807-24.html
# https://item.rakuten.co.jp/cocodecow/r820gf/
# https://store.shopping.yahoo.co.jp/cocodecow/y388eb.html
# https://shimojima.live/shop/g/g2501600064181/
EXPANSION_YAHOO_JAN = {"mineral-water": "4510892001338"}

def expansion_price_preview(candidates, matches, spec, checked_at, now=None):
    """Require unique listings, fresh prices and explicit shipping safety; never publish."""
    now = now or datetime.now(timezone.utc)
    result = {"status": "NOT_COMPARABLE", "publish_allowed": False}
    try:
        stamp = datetime.fromisoformat(checked_at)
        if stamp.tzinfo is None or not timedelta(hours=-1) <= now-stamp <= timedelta(hours=48):
            return dict(result, reason="STALE_OR_INVALID_RAKUTEN_TIMESTAMP")
    except (TypeError, ValueError):
        return dict(result, reason="STALE_OR_INVALID_RAKUTEN_TIMESTAMP")
    if len(candidates) != 1 or len(matches) != 1:
        return dict(result, reason="AMBIGUOUS_OR_MISSING_LISTING")
    r, y = candidates[0], matches[0]
    expected = EXPANSION_YAHOO_JAN.get(spec[0])
    if expected and y.get("janCode") != expected:
        return dict(result, reason="YAHOO_JAN_UNVERIFIED")
    link = safe_url(r.get("url"))
    if (not link or link.scheme != "https" or link.hostname != "hb.afl.rakuten.co.jp"
            or type(r.get("price")) is not int or r["price"] <= 0):
        return dict(result, reason="RAKUTEN_PRICE_OR_LINK_UNVERIFIED")
    shipping = y.get("shipping")
    terms = " ".join(normalize(y.get(k)) for k in ("name", "headLine", "description"))
    terms += " " + normalize(r.get("name")) + " " + normalize(r.get("raw_name"))
    if (not isinstance(shipping, dict) or shipping.get("code") != 2
            or SHIPPING_CONDITIONS.search(terms + " " + normalize(shipping.get("name")))):
        return dict(result, reason="SHIPPING_CONDITIONS_REQUIRE_REVIEW")
    divisor = spec[11] / (100 if spec[0] == "pasta" else 1000)
    return dict(result, status="API_PRICE_PREVIEW_ONLY",
                identity_basis="merchant_sku" if not expected else "reviewed_listing_and_yahoo_jan",
                rakuten_listed_price_yen=r["price"], yahoo_listed_price_yen=y["price"],
                unit="100g" if spec[0] == "pasta" else "1L",
                rakuten_unit_price_yen=round(r["price"]/divisor, 2),
                yahoo_unit_price_yen=round(y["price"]/divisor, 2),
                checkout_total_verified=False)

def expansion_report(catalog, app_id, affiliate_id, request=fetch):
    """Report candidate counts only; no publication and no logging of links."""
    if not app_id or not affiliate_id:
        return {"status": "NOT_CONFIGURED"}
    try:
        prefix, sid, pid = affiliate_config(affiliate_id)
        if sid != "3790012":
            return {"status": "WRONG_SITE"}
    except Exception:
        return {"status": "INVALID_CONFIG"}
    out = {}
    for index, spec in enumerate(EXPANSION):
        if index:
            time.sleep(2.5)
        category, rid, path, ycode, query = spec[:5]
        try:
            rows = catalog["categories"][category]["included"]
            candidates = []
            for row in rows:
                q = row.get("quantity", {})
                targets = parse_qs(urlsplit(row.get("url", "")).query).get("pc", [])
                if len(targets) != 1:
                    continue
                target = urlsplit(targets[0])
                if (row.get("id") == rid and target.scheme == "https" and target.netloc == "item.rakuten.co.jp"
                        and target.path == path and row.get("shipping_status") == "included"
                        and row.get("postage_included") is True and expansion_title(row.get("name"), spec)
                        and q.get(spec[8]) == spec[9] and q.get(spec[10]) == spec[11] and q.get("count") == spec[12]):
                    candidates.append(row)
            hits = request(None, app_id, affiliate_prefix=prefix, query=query)
            if not isinstance(hits, list) or any(not isinstance(h, dict) for h in hits):
                raise ValueError("schema")
            matches = [h for h in hits if h.get("code") == ycode and expansion_title(h.get("name"), spec)
                       and affiliate_target(h, app_id, sid, pid) and h.get("inStock") is True
                       and h.get("condition") == "new" and type(h.get("price")) is int and h["price"] > 0
                       and isinstance(h.get("priceLabel"), dict) and h["priceLabel"].get("taxable") is True]
            free = [h for h in matches if isinstance(h.get("shipping"), dict) and h["shipping"].get("code") == 2
                    and not SHIPPING_CONDITIONS.search(" ".join(normalize(h.get(k)) for k in ("name","headLine","description")))]
            out[category] = {"rakuten_listing_matches":len(candidates), "yahoo_ad_listing_matches":len(matches),
                             "yahoo_shipping_flag_candidates":len(free), "publish_allowed":False,
                             "price_preview":expansion_price_preview(candidates, matches, spec, catalog.get("generated_at"))}
        except Exception:
            out[category] = {"status":"UNAVAILABLE", "publish_allowed":False}
    return out


# Bounded read-only discovery: never turn title similarity into a public offer.
DISCOVERY_CATEGORIES = ("rice", "carbonated-water", "oatmeal", "granola",
                        "retort-curry", "bag-noodles", "cup-noodles")
DISCOVERY_LIMIT = 3

def discovery_listing(row):
    link = safe_url(row.get("url"))
    if not link or link.scheme != "https" or link.hostname != "hb.afl.rakuten.co.jp":
        return None
    targets = parse_qs(link.query).get("pc", [])
    target = safe_url(targets[0]) if len(targets) == 1 else None
    if not target or target.scheme != "https" or target.hostname != "item.rakuten.co.jp":
        return None
    match = re.fullmatch(r"/([a-zA-Z0-9_-]+)/([a-zA-Z0-9._-]+)/?", target.path)
    if not match or not str(row.get("id", "")).startswith(match[1]+":"):
        return None
    if row.get("shipping_status") != "included" or row.get("postage_included") is not True:
        return None
    if type(row.get("price")) is not int or row["price"] <= 0:
        return None
    title = normalize(row.get("name"))
    if not title or SHIPPING_CONDITIONS.search(title + " " + normalize(row.get("raw_name"))):
        return None
    if re.search(r"訳あり|賞味期限間近|選べる|選択|詰め合わせ|定期|ふるさと納税|初回限定", title):
        return None
    return match[1] + "_" + match[2]

def discovery_signature(quantity):
    keys = ("unit_weight_g", "total_weight_g", "unit_volume_ml", "total_volume_ml", "count")
    if not isinstance(quantity, dict) or type(quantity.get("count")) is not int or quantity["count"] <= 0:
        return None
    values = tuple(quantity.get(k) for k in keys)
    if any(v is not None and (type(v) not in (int, float) or v <= 0) for v in values):
        return None
    return values

def discovery_title(name):
    # Remove only generic shipping words and whitespace; preserve all variant terms.
    return re.sub(r"[\s【】\[\]（）()]|送料無料|送料込み", "", normalize(name))

def discovery_report(catalog, app_id, affiliate_id, request=fetch, *, limit=DISCOVERY_LIMIT, pause=time.sleep, offsets=None):
    """Bounded discovery; report public SKU identifiers and rejection reasons, never ad URLs."""
    if not app_id or not affiliate_id:
        return {"status": "NOT_CONFIGURED"}
    try:
        prefix, sid, pid = affiliate_config(affiliate_id)
        if sid != "3790012":
            return {"status": "WRONG_SITE"}
    except Exception:
        return {"status": "INVALID_CONFIG"}
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from build_site import parse_quantity
    from product_quality import category_rejection, quantity_conflict
    from new_food import RULES, rejection as new_rejection
    out = {}
    details = {}
    calls = 0
    for category in DISCOVERY_CATEGORIES:
        counts = {"eligible": 0, "queried": 0, "sku_matches": 0,
                  "quantity_matches": 0, "strict_candidates": 0, "errors": 0}
        rows = catalog.get("categories", {}).get(category, {}).get("included", [])
        seen = set()
        details[category] = []
        offset = max(0, int((offsets or {}).get(category, 0)))
        for row in rows:
            code = discovery_listing(row)
            q = discovery_signature(row.get("quantity"))
            if not code or not q or code in seen:
                continue
            seen.add(code)
            counts["eligible"] += 1
            if counts["eligible"] <= offset or counts["queried"] >= max(0, min(limit, DISCOVERY_LIMIT)):
                continue
            if calls:
                pause(2.5)
            calls += 1
            counts["queried"] += 1
            item = {"sku":code,"result":"unavailable"}
            details[category].append(item)
            try:
                store = str(row["id"]).split(":",1)[0]
                hits = request(None, app_id, affiliate_prefix=prefix, query=code[len(store)+1:])
                if not isinstance(hits, list) or any(not isinstance(h, dict) for h in hits):
                    raise ValueError("schema")
                sku_hits = [h for h in hits if h.get("code") == code]
                matched = [h for h in sku_hits if affiliate_target(h, app_id, sid, pid)]
                if len(sku_hits) != 1 or len(matched) != 1:
                    item["result"] = "sku_missing" if not sku_hits else "sku_ambiguous" if len(sku_hits) != 1 else "ad_invalid"
                    continue
                counts["sku_matches"] += 1
                h = matched[0]
                name = h.get("name")
                if not isinstance(name, str):
                    item["result"] = "missing_title"
                    continue
                reject = new_rejection(category, name) if category in RULES else category_rejection(category, name)
                parsed = parse_quantity(name, category)
                if reject or not parsed or quantity_conflict(name, category, parsed) or discovery_signature(parsed) != q:
                    item["result"] = "category_rejected" if reject else "quantity_unverified"
                    continue
                counts["quantity_matches"] += 1
                shipping = h.get("shipping")
                terms = " ".join(normalize(h.get(k)) for k in ("name","headLine","description"))
                reasons = []
                if discovery_title(name) != discovery_title(row.get("name")):
                    reasons.append("title_mismatch")
                if h.get("inStock") is not True or h.get("condition") != "new":
                    reasons.append("stock_or_condition")
                if type(h.get("price")) is not int or h["price"] <= 0 or not isinstance(h.get("priceLabel"), dict) or h["priceLabel"].get("taxable") is not True:
                    reasons.append("price_or_tax_unverified")
                if not isinstance(shipping, dict) or shipping.get("code") != 2:
                    reasons.append("shipping_flag")
                elif SHIPPING_CONDITIONS.search(terms + " " + normalize(shipping.get("name"))):
                    reasons.append("shipping_conditions")
                if reasons:
                    item["result"] = "rejected"
                    item["reasons"] = reasons
                else:
                    counts["strict_candidates"] += 1
                    item["result"] = "strict_candidate"
                    item["rakuten_id"] = row["id"]
                    item["rakuten_price_yen"] = row["price"]
                    item["yahoo_price_yen"] = h["price"]
            except Exception:
                counts["errors"] += 1
        out[category] = counts
    return {"categories":out, "details":details, "api_calls":calls, "publish_allowed":False}

if __name__ == "__main__":
    catalog = json.loads(Path("data/products.json").read_text(encoding="utf-8"))
    app_id = os.getenv("YAHOO_APP_ID", "").strip()
    affiliate_id = os.getenv("YAHOO_AFFILIATE_ID", "").strip()
    result = report(catalog, app_id)
    if affiliate_id and result["status"] == "OK":
        time.sleep(2.5)
    result["affiliate_validation"] = (affiliate_probe(app_id, affiliate_id)
                                      if result["status"] == "OK" else {"status": "SKIPPED", "publish_allowed": False})
    if affiliate_id and result["status"] == "OK":
        time.sleep(2.5)
        result["expansion"] = expansion_report(catalog, app_id, affiliate_id)
    if affiliate_id and result["status"] == "OK":
        time.sleep(2.5)
        result["discovery"] = discovery_report(catalog, app_id, affiliate_id, offsets={
            "carbonated-water":3, "oatmeal":3, "bag-noodles":3, "cup-noodles":3})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "OK" else 1)
