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



def render_quantity_only_planner() -> str:
    """Supply-gap fallback: pure counts and stock, never guessed prices or offers."""
    choices = ''.join(
        f'<button type="button" class="rice-meal-choice" data-rice-quantity-choice="{n}" '
        f'aria-pressed="{str(n == 1).lower()}">{n}食/日</button>'
        for n in (1, 2, 3, 4)
    )
    return f'''<section class="section rice-planner rice-quantity-only" data-rice-quantity-only
aria-labelledby="rice-quantity-title">
<div class="rice-planner-intro"><span class="rice-planner-kicker">QUANTITY ONLY</span>
<h2 id="rice-quantity-title">24食入りなら、何箱必要？</h2>
<p>現在、販売条件を確認できる24食セットがないため、商品価格・販売先・送料・購入リンクは表示できません。
箱数だけ計算できます。</p></div>
<div class="rice-planner-body">
<form class="rice-planner-form" data-rice-quantity-form novalidate>
<label for="rice-quantity-daily">1日に使う食数（世帯合計）</label>
<div class="rice-meal-choices" role="group" aria-label="1日に使う食数">{choices}</div>
<div class="rice-planner-number"><input id="rice-quantity-daily" data-rice-quantity-daily type="number"
min="1" max="24" step="1" value="1" inputmode="numeric" aria-describedby="rice-quantity-error"><span>食/日</span></div>
<label for="rice-quantity-days">何日分を用意する？</label>
<div class="rice-planner-number"><input id="rice-quantity-days" data-rice-quantity-days type="number"
min="1" max="90" step="1" value="30" inputmode="numeric" aria-describedby="rice-quantity-error"><span>日</span></div>
<label for="rice-quantity-stock">期限内に使える手持ちの食数</label>
<div class="rice-planner-number"><input id="rice-quantity-stock" data-rice-quantity-stock type="number"
min="0" max="100000" step="1" value="0" inputmode="numeric" aria-describedby="rice-quantity-error"><span>食</span></div>
<p class="rice-planner-help">利用量は自分で入力。食生活の推奨ではありません。入力内容は保存・送信しません。</p>
<p class="rice-planner-error" id="rice-quantity-error" data-rice-quantity-error role="alert" hidden>
1日の食数は1〜24、日数は1〜90、手持ちは0〜100000食の整数で入力してください。</p>
</form>
<div class="rice-planner-results" data-rice-quantity-result aria-live="polite" aria-atomic="true">
<p class="rice-planner-decision" data-rice-quantity-summary>30食必要。手持ち0食を差し引くと30食不足します。</p>
<div class="rice-planner-grid"><div><span>必要な食数</span><strong data-rice-quantity-needed>30食</strong></div>
<div><span>不足する食数</span><strong data-rice-quantity-shortage>30食</strong></div>
<div><span>24食入りの場合に必要な箱数</span><strong data-rice-quantity-boxes>2箱</strong></div>
<div><span>用意後に余る食数</span><strong data-rice-quantity-leftover>18食</strong></div></div>
<p class="rice-planner-detail">これは24食入りの箱を選ぶ場合の数量計算です。
商品候補・1食の重さ・販売価格・送料・賞味期限は未確認のため、支払総額は計算できません。</p>
</div></div></section>'''



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
    <div class="rice-meal-choices" role="group" aria-label="1日に使う食数を選ぶ">
      {''.join(f'<button type="button" class="rice-meal-choice" data-rice-meal-choice="{n}" aria-pressed="{str(n==1).lower()}">{n}食/日</button>' for n in (1, 2, 3, 4))}
    </div>
    <div class="rice-planner-number"><input id="rice-meals-day" type="number" name="meals_per_day"
      min="1" max="24" step="1" value="1" inputmode="numeric" required
      aria-describedby="rice-planner-help rice-planner-error"><span>食／日</span></div>
    <p id="rice-planner-help" class="rice-planner-help">1〜24食の整数で入力してください。1か月は30日として計算します。</p>
    <label for="rice-stock-meals">いま使える手持ちのご飯（食数）</label>
    <div class="rice-planner-number"><input id="rice-stock-meals" data-rice-stock-input type="number"
      name="stock_meals" min="0" max="100000" step="1" value="0" inputmode="numeric" required
      aria-describedby="rice-stock-help rice-planner-error"><span>食</span></div>
    <p id="rice-stock-help" class="rice-planner-help">消費期限内に食べられる同じ用途の在庫だけ入力。保存・送信はしません。</p>
    <label for="rice-planner-product">比較する24食セット</label>
    <select id="rice-planner-product" data-rice-planner-product>
      {''.join(options)}
    </select>
    <p class="rice-planner-help">表示は実際に掲載中の送料込み商品から選択。並び順は元の1食単価ランキングと同じです。</p>
    <p id="rice-planner-error" class="rice-planner-error" data-rice-planner-error role="alert" hidden>使用量は1〜24食、手持ちは0〜100000食の整数で入力してください。掲載条件も確認してください。</p>
  </form>
  <div class="rice-planner-results" data-rice-planner-results aria-live="polite" aria-atomic="true">
    <div class="rice-planner-highlight"><span>この1箱が持つ期間</span><strong data-rice-days>{calc["days_per_box"]:g}日</strong></div>
    <p class="rice-planner-decision" data-rice-recommendation>手持ちを差し引くと30食不足します。購入時は2箱分の金額が必要です。</p>
    <div class="rice-planner-grid">
      <div><span>買い足しが必要な食数</span><strong data-rice-shortage>30食</strong></div>
      <div><span>必要な購入箱数</span><strong data-rice-boxes>{calc["boxes"]}箱</strong></div>
      <div><span>購入時の支払総額</span><strong data-rice-purchase>¥{calc["purchase_total"]:,}</strong></div>
      <div><span>購入後・30日後に残る食数</span><strong data-rice-leftover>{calc["remaining_meals"]}食</strong></div>
      <div><span>1食あたりの価格</span><strong data-rice-unit>¥{calc["one_meal_price"]:,.1f}</strong></div>
    </div>
    <p data-rice-detail class="rice-planner-detail">1食 {first["quantity"]["unit_weight_g"]:g}g。買い足し対象の30食分の価格換算は
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
<p class="rice-planner-disclaimer">計算式：30日分の必要食数から入力した在庫食数を差し引き、不足食数 ÷ 1箱24食を切り上げ、必要箱数 × 取得時の商品価格。
残りは手持ち在庫と買った箱数から30日分の食数を引いた値です。消費期限・保管場所・食べる日数を保証するものではありません。
実際の価格・地域別追加送料・在庫は購入前に販売店で確認してください。
価格確認：{updated:%Y-%m-%d %H:%M} JST。</p>
<p class="rice-planner-examples"><strong>計算例：</strong>24食セットなら、1日1食で24日分・30日間では2箱必要。
1日2食なら12日分・30日間では3箱必要です。</p>
</section>'''
