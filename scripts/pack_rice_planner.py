"""24-meal pack-rice shopping planner; only published, verified offers.

This module never selects prices independently of the existing food catalog.
"""
from __future__ import annotations

import html
import math
from datetime import datetime
from urllib.parse import urlsplit


def calculation(count: int, price: int, meals_per_day: int, period_days: int = 30) -> dict:
    """Deterministic purchase planning, distinct from prorated consumption cost."""
    if (not 1 <= int(count) <= 10000 or not 1 <= int(meals_per_day) <= 24
            or not 1 <= int(period_days) <= 366 or int(price) <= 0):
        raise ValueError("positive published quantity, price and usage required")
    if not all(isinstance(x, int) for x in (count, price, meals_per_day, period_days)):
        raise ValueError("integer inputs required")
    total = meals_per_day * period_days
    boxes = math.ceil(total / count)
    return {
        "days_per_box": count / meals_per_day,
        "meals_needed": total,
        "boxes": boxes,
        "purchase_total": boxes * price,
        "remaining_meals": boxes * count - total,
        "one_meal_price": price / count,
        "consumption_cost": total * price / count,
    }


def render_planner(items: list[dict], updated: datetime) -> str:
    """Show a useful above-the-fold tool for verified 24-meal offers only."""
    eligible = []
    for row in items:
        quantity = row.get("quantity") or {}
        count = quantity.get("count")
        grams = quantity.get("unit_weight_g")
        price = row.get("price")
        if (count == 24 and isinstance(count, int)
                and isinstance(price, int) and price > 0
                and isinstance(grams, (int, float)) and math.isfinite(grams) and grams > 0
                and row.get("postage_included") is True
                and row.get("shipping_status") == "included"
                and isinstance(row.get("url"), str)
                and urlsplit(row["url"]).scheme == "https"
                and (urlsplit(row["url"]).hostname or "").endswith(".rakuten.co.jp")):
            eligible.append(row)
    if not eligible:
        return ""

    options = []
    for rank, item in enumerate(eligible, 1):
        count, price = item["quantity"]["count"], item["price"]
        grams = item["quantity"]["unit_weight_g"]
        name = item["name"]
        # Actual rankings are unchanged; no invented ratings or recommendations.
        display = name if len(name) <= 48 else name[:47].rstrip() + "…"
        label = f"{rank}位｜{grams:g}g × {count}食｜{price:,}円｜{display}"
        option = (
            f'<option value="{rank - 1}" data-price="{price}" data-count="{count}" '
            f'data-grams="{grams:g}" data-product-id="{html.escape(str(item["id"]), quote=True)}" '
            f'data-product-name="{html.escape(name, quote=True)}" '
            f'data-unit-price="{price / count:.6f}" '
            f'data-product-url="{html.escape(item["url"], quote=True)}" data-rank="{rank}">'
            f'{html.escape(label)}</option>'
        )
        options.append(option)

    first = eligible[0]
    calc = calculation(24, first["price"], 1)
    return f'''<section id="pack-rice-planner" class="section rice-planner" data-rice-planner aria-labelledby="rice-planner-title">
<div class="rice-planner-intro">
  <span class="rice-planner-kicker">24-MEAL STOCK PLANNER</span>
  <h2 id="rice-planner-title">24食のパックご飯、うちでは何日持つ？</h2>
  <p>1日に使う食数を入力すると、30日分の必要箱数・購入総額・残る食数を計算します。
  商品ごとに1食の重さが違うため、容量も合わせて確認できます。</p>
</div>
<div class="rice-planner-body">
  <form class="rice-planner-form" data-rice-planner-form novalidate>
    <label for="rice-meals-day">1日に食べる量（家族・世帯合計）</label>
    <div class="rice-planner-number"><input id="rice-meals-day" type="number" name="meals_per_day"
      min="1" max="24" step="1" value="1" inputmode="numeric" required
      aria-describedby="rice-planner-help rice-planner-error"><span>食／日</span></div>
    <p id="rice-planner-help" class="rice-planner-help">1〜24食の整数で入力してください。1か月は30日として計算します。</p>
    <label for="rice-planner-product">比較する24食セット</label>
    <select id="rice-planner-product" data-rice-planner-product>
      {''.join(options)}
    </select>
    <p class="rice-planner-help">表示は実際に掲載中の送料込み商品から選択。並び順は元の1食単価ランキングと同じです。</p>
    <p id="rice-planner-error" class="rice-planner-error" data-rice-planner-error role="alert" hidden>1〜24食の整数を入力してください。</p>
  </form>
  <div class="rice-planner-results" data-rice-planner-results aria-live="polite" aria-atomic="true">
    <div class="rice-planner-highlight"><span>この1箱が持つ期間</span><strong data-rice-days>{calc["days_per_box"]:g}日</strong></div>
    <div class="rice-planner-grid">
      <div><span>30日分の必要箱数</span><strong data-rice-boxes>{calc["boxes"]}箱</strong></div>
      <div><span>購入時の支払総額</span><strong data-rice-purchase>¥{calc["purchase_total"]:,}</strong></div>
      <div><span>30日後に残る食数</span><strong data-rice-leftover>{calc["remaining_meals"]}食</strong></div>
      <div><span>1食あたりの価格</span><strong data-rice-unit>¥{calc["one_meal_price"]:,.1f}</strong></div>
    </div>
    <p data-rice-detail class="rice-planner-detail">1食 {first["quantity"]["unit_weight_g"]:g}g。30日間に使う30食分の価格換算は
    ¥{calc["consumption_cost"]:,.1f}。箱単位の購入総額とは異なります。</p>
    <a class="rice-planner-buy" data-rice-planner-buy
       href="{html.escape(first["url"], quote=True)}" target="_blank" rel="nofollow sponsored noopener"
       data-affiliate="rakuten" data-position="usage_planner" data-category="pack-rice"
       data-product-id="{html.escape(str(first["id"]), quote=True)}"
       data-product-name="{html.escape(first["name"], quote=True)}"
       data-rank="1" data-metric="per_serving"
       data-unit-price="{first["price"] / 24:.6f}" data-shipping="included" data-cta-variant="usage_planner">
       選んだ商品を楽天で確認する →
    </a>
  </div>
</div>
<p class="rice-planner-disclaimer">計算式：30日分の必要食数 ÷ 1箱24食を切り上げ、必要箱数 × 取得時の商品価格。
残りは買った箱数から30日分の食数を引いた値です。消費期限・保管場所・食べる日数を保証するものではありません。
実際の価格・地域別追加送料・在庫は購入前に販売店で確認してください。
価格確認：{updated:%Y-%m-%d %H:%M} JST。</p>
<p class="rice-planner-examples"><strong>計算例：</strong>24食セットなら、1日1食で24日分・30日間では2箱必要。
1日2食なら12日分・30日間では3箱必要です。</p>
</section>'''
