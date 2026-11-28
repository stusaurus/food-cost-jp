"""Opt-in, same-SKU comparison. No Yahoo offer enters the Rakuten ranking."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import html
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qs

# Reuse the already tested probe, rather than duplicate identity/price rules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analytics"))
from yahoo_pack_rice_probe import (
    PRODUCTS, affiliate_config, affiliate_target, exact_sato_rakuten,
    exact_sato_yahoo, fetch, price_pair_preview, EXPANSION, expansion_title,
    expansion_price_preview, safe_url,
)

FOOD_SITE_ID = "3790012"  # Public site identifier; not an API credential.

@dataclass(frozen=True)
class VerifiedPair:
    rakuten_price: int
    yahoo_price: int
    rakuten_url: str
    yahoo_url: str
    rakuten_checked: str
    yahoo_checked: str
    category: str = "pack-rice"

# Category, display name, set label, divisor, unit, metric, retailer IDs.
PAIR_SPECS = {
    "pack-rice": ("サトウのごはん 銀シャリ 200g×80食", "80食セット", 80, "1食", "per_serving", "likaman:10040020", "likaman_950871-16"),
    "pasta": ("ディチェコ No.12 500g×24袋", "12kgセット", 120, "100g", "per_100g", "likaman:10033183", "likaman_927807-24"),
    "mineral-water": ("安曇野の天然水 2L×12本", "24Lセット", 24, "1L", "per_liter", "cocodecow:10778153", "cocodecow_y388eb"),
    "granola": ("カルビー フルグラ 700g×6袋", "4.2kgセット", 42, "100g", "per_100g", "okagesama-market:10003972", "okagesama-market_4901330748296"),
}

def collect_pair(rows, checked_at, app_id="", affiliate_id="", *, approved=False, request=fetch, now=None):
    """Only approved, live, verified food-site credentials can produce a pair."""
    if approved is not True or not app_id or not affiliate_id:
        return None
    try:
        prefix, sid, pid = affiliate_config(affiliate_id)
        if sid != FOOD_SITE_ID:
            return None
        product = PRODUCTS[1]
        hits = request(product[1], app_id, affiliate_prefix=prefix)
        if not isinstance(hits, list) or any(not isinstance(h, dict) for h in hits):
            return None
        matched = []
        for hit in hits:
            target = affiliate_target(hit, app_id, sid, pid)
            if target and exact_sato_yahoo([dict(hit, url=target)], product):
                matched.append((dict(hit, url=target), hit["url"]))
        if len(matched) != 1:
            return None
        preview = price_pair_preview(rows, [matched[0][0]], product, checked_at, now)
        if preview["status"] != "API_PRICE_PREVIEW_ONLY":
            return None
        r = [row for row in rows if exact_sato_rakuten([row], product)]
        if len(r) != 1:
            return None
        return VerifiedPair(r[0]["price"], matched[0][0]["price"], r[0]["url"],
                            urlunsplit(urlsplit(matched[0][1])._replace(scheme="https")),
                            preview["rakuten_checked_at"], preview["yahoo_checked_at"])
    except Exception:
        # Optional functionality never prevents the existing catalog publication.
        return None

def collect_expansion_pair(category, rows, checked_at, app_id="", affiliate_id="", *, approved=False, request=fetch, now=None):
    """Use reviewed exact listings, current prices, food-specific ads and fail-closed gates."""
    if approved is not True or not app_id or not affiliate_id:
        return None
    try:
        spec = next(s for s in EXPANSION if s[0] == category)
        prefix, sid, pid = affiliate_config(affiliate_id)
        if sid != FOOD_SITE_ID:
            return None
        candidates = []
        for row in rows:
            link = safe_url(row.get("url"))
            if not link or link.scheme != "https" or link.hostname != "hb.afl.rakuten.co.jp":
                continue
            targets = parse_qs(link.query).get("pc", [])
            target = safe_url(targets[0]) if len(targets) == 1 else None
            q = row.get("quantity", {})
            if (row.get("id") == spec[1] and target and target.scheme == "https"
                    and target.hostname == "item.rakuten.co.jp" and target.path == spec[2]
                    and row.get("shipping_status") == "included" and row.get("postage_included") is True
                    and expansion_title(row.get("name"), spec)
                    and q.get(spec[8]) == spec[9] and q.get(spec[10]) == spec[11]
                    and q.get("count") == spec[12]):
                candidates.append(row)
        if len(candidates) != 1:
            return None
        hits = request(None, app_id, affiliate_prefix=prefix, query=spec[4])
        if not isinstance(hits, list) or any(not isinstance(h, dict) for h in hits):
            return None
        matches = [h for h in hits if h.get("code") == spec[3] and expansion_title(h.get("name"), spec)
                   and affiliate_target(h, app_id, sid, pid) and h.get("inStock") is True
                   and h.get("condition") == "new" and type(h.get("price")) is int and h["price"] > 0
                   and isinstance(h.get("priceLabel"), dict) and h["priceLabel"].get("taxable") is True]
        now = now or datetime.now(timezone.utc)
        preview = expansion_price_preview(candidates, matches, spec, checked_at, now)
        if preview["status"] != "API_PRICE_PREVIEW_ONLY":
            return None
        r, y = candidates[0], matches[0]
        return VerifiedPair(r["price"], y["price"], r["url"],
                            urlunsplit(urlsplit(y["url"])._replace(scheme="https")),
                            checked_at, now.isoformat(), category)
    except Exception:
        return None


def render_pair(pair, now=None):
    if not isinstance(pair, VerifiedPair):
        return ""
    now = now or datetime.now(timezone.utc)
    try:
        stamps = [datetime.fromisoformat(s) for s in (pair.rakuten_checked, pair.yahoo_checked)]
        if any(s.tzinfo is None or not timedelta(hours=-1) <= now-s <= timedelta(hours=48) for s in stamps):
            return ""
        if any(type(p) is not int or p <= 0 for p in (pair.rakuten_price, pair.yahoo_price)):
            return ""
    except (ValueError, TypeError):
        return ""
    if pair.category not in PAIR_SPECS:
        return ""
    product, set_label, divisor, unit, metric, rid, yid = PAIR_SPECS[pair.category]
    esc = html.escape
    delta = abs(pair.rakuten_price - pair.yahoo_price)
    winner = ("楽天市場" if pair.rakuten_price < pair.yahoo_price else
              "Yahoo!ショッピング" if pair.yahoo_price < pair.rakuten_price else "")
    summary = f"{winner}の掲載価格が{delta:,}円安い" if winner else "両モールの掲載価格は同額"
    def offer(market, name, price, url, sku, stamp):
        return (f'<div class="intent-card"><strong>{name}</strong>'
                f'<p><strong>{price:,}円</strong>（{set_label}）</p>'
                f'<p>{unit} {price/divisor:,.2f}円</p>'
                f'<p class="fine">確認時刻：{esc(datetime.fromisoformat(stamp).astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M"))} JST</p>'
                f'<a class="finder-go" href="{esc(url, quote=True)}" target="_blank" rel="nofollow sponsored noopener" '
                f'data-affiliate="{market}" data-position="marketplace_comparison" data-category="{pair.category}" '
                f'data-product-id="{sku}" data-product-name="{esc(product, quote=True)}" '
                f'data-metric="{metric}" data-unit-price="{price/divisor:.2f}" data-shipping="included_flag">販売店で確認 →</a></div>')
    expiry = (min(stamps)+timedelta(hours=48)).isoformat()
    return (f'<section class="section explain" id="marketplace-comparison" data-price-expiry="{esc(expiry)}">'
            f'<h2>同じ商品を楽天・Yahoo!で比較</h2><p>{esc(product)}</p>'
            f'<p><strong>{summary}</strong></p><div class="intent-grid">'
            + offer("rakuten", "楽天市場", pair.rakuten_price, pair.rakuten_url, rid, pair.rakuten_checked)
            + offer("yahoo", "Yahoo!ショッピング", pair.yahoo_price, pair.yahoo_url, yid, pair.yahoo_checked)
            + '</div><p class="fine">税込掲載価格・送料無料フラグで比較。配送先別の追加送料、在庫、ポイント・クーポン、最終支払額は販売店で確認してください。広告リンクを含みます。</p></section>')
