"""Opt-in, same-SKU comparison. No Yahoo offer enters the Rakuten ranking."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import html
import sys
from urllib.parse import urlsplit, urlunsplit

# Reuse the already tested probe, rather than duplicate identity/price rules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analytics"))
from yahoo_pack_rice_probe import (
    PRODUCTS, affiliate_config, affiliate_target, exact_sato_rakuten,
    exact_sato_yahoo, fetch, price_pair_preview,
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
    esc = html.escape
    delta = abs(pair.rakuten_price - pair.yahoo_price)
    winner = ("楽天市場" if pair.rakuten_price < pair.yahoo_price else
              "Yahoo!ショッピング" if pair.yahoo_price < pair.rakuten_price else "")
    summary = f"{winner}の掲載価格が{delta:,}円安い" if winner else "両モールの掲載価格は同額"
    def offer(market, name, price, url, sku, stamp):
        return (f'<div class="intent-card"><strong>{name}</strong>'
                f'<p><strong>{price:,}円</strong>（80食セット）</p>'
                f'<p>1食 {price/80:,.2f}円</p>'
                f'<p class="fine">確認時刻：{esc(datetime.fromisoformat(stamp).astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M"))} JST</p>'
                f'<a class="finder-go" href="{esc(url, quote=True)}" target="_blank" rel="nofollow sponsored noopener" '
                f'data-affiliate="{market}" data-position="marketplace_comparison" data-category="pack-rice" '
                f'data-product-id="{sku}" data-product-name="サトウのごはん 銀シャリ 200g×80食" '
                f'data-metric="per_serving" data-unit-price="{price/80:.2f}" data-shipping="included_flag">販売店で確認 →</a></div>')
    expiry = (min(stamps)+timedelta(hours=48)).isoformat()
    return (f'<section class="section explain" id="marketplace-comparison" data-price-expiry="{esc(expiry)}">'
            '<h2>同じ商品を楽天・Yahoo!で比較</h2><p>サトウのごはん 銀シャリ 200g×5食×16袋（80食）</p>'
            f'<p><strong>{summary}</strong></p><div class="intent-grid">'
            + offer("rakuten", "楽天市場", pair.rakuten_price, pair.rakuten_url, "likaman:10040020", pair.rakuten_checked)
            + offer("yahoo", "Yahoo!ショッピング", pair.yahoo_price, pair.yahoo_url, "likaman_950871-16", pair.yahoo_checked)
            + '</div><p class="fine">税込掲載価格・送料無料フラグで比較。配送先別の追加送料、在庫、ポイント・クーポン、最終支払額は販売店で確認してください。広告リンクを含みます。</p></section>')
