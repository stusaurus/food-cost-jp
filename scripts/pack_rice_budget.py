"""24食パックご飯の購入量シミュレーター（表示専用）。

既存の送料込み検証済み24食候補を利用する。価格予想や商品推奨は行わない。
"""
from __future__ import annotations

import html
import math
from pathlib import Path

from product_display import clean_display_name


def budget_projection(price: float, count: int, meals_per_day: float) -> dict:
    """30日分の必要食数・箱単位の支払額。端数は箱単位で切り上げる。"""
    if (not math.isfinite(price) or price <= 0 or count <= 0
            or not math.isfinite(meals_per_day) or not 0.5 <= meals_per_day <= 12):
        raise ValueError("invalid budget input")
    monthly_meals = meals_per_day * 30
    boxes = math.ceil(monthly_meals / count)
    return {
        "days_per_box": count / meals_per_day,
        "monthly_meals": monthly_meals,
        "boxes": boxes,
        "total_payment": price * boxes,
        "remaining_meals": boxes * count - monthly_meals,
        "per_meal": price / count,
    }


def valid_candidates(items: list[dict]) -> list[dict]:
    """商品取得側ですでに検証した24食セットから、数値の確実なものだけを使う。"""
    result = []
    for row in items:
        try:
            count = int(row["quantity"]["count"])
            price = float(row["price"])
            grams = float(row["quantity"]["unit_weight_g"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if (count == 24 and math.isfinite(price) and price > 0
                and math.isfinite(grams) and grams > 0
                and row.get("postage_included") is True):
            result.append({"item": row, "count": count, "price": price, "grams": grams})
    return result


def budget_panel(items: list[dict]) -> str:
    candidates = valid_candidates(items)
    if not candidates:
        return ""
    first = candidates[0]
    baseline = budget_projection(first["price"], first["count"], 1)
    choices = []
    for i, row in enumerate(candidates):
        item = row["item"]
        label = clean_display_name(item.get("name") or "商品名未確認")
        label = label[:46] + ("…" if len(label) > 46 else "")
        choices.append(
            '<option value="{i}" data-price="{price:.2f}" data-count="{count}" '
            'data-grams="{grams:g}">{label}｜{grams:g}g×24食・1食 約¥{unit:,.0f}</option>'.format(
                i=i, price=row["price"], count=row["count"], grams=row["grams"],
                label=html.escape(label, quote=True), unit=row["price"] / row["count"]))
    return """<section class="budget-panel section" id="pack-rice-budget" data-pack-rice-budget
 aria-labelledby="pack-rice-budget-title">
<div class="budget-kicker">24食を自分の生活に当てはめる</div>
<h2 id="pack-rice-budget-title">1日何食？ 24食が何日持つか計算</h2>
<p class="budget-lead">実際に掲載している24食セットを選び、1日の平均食数を入力すると、30日分に必要な箱数と支払総額を計算します。</p>
<form class="budget-form" data-budget-form novalidate>
<div class="budget-field">
<label for="pack-rice-budget-product">比較する24食セット</label>
<select id="pack-rice-budget-product" data-budget-product>{options}</select>
</div>
<div class="budget-field budget-field-small">
<label for="pack-rice-meals-per-day">1日あたりの平均食数</label>
<div class="budget-number"><input id="pack-rice-meals-per-day" data-budget-daily type="number"
 min="0.5" max="12" step="0.5" value="1" inputmode="decimal" required><span>食／日</span></div>
<small>0.5〜12食。週に数回なら0.5など、小数でも入力できます。</small>
</div>
<button class="budget-calculate" type="submit">この条件で計算する</button>
<p class="budget-error" data-budget-error role="alert" hidden></p>
</form>
<div class="budget-results" data-budget-results aria-live="polite" aria-atomic="true">
<div class="budget-result budget-result-primary"><span>24食が持つ日数</span><strong data-budget-days>{days:g}日</strong></div>
<div class="budget-result"><span>30日間に必要な食数</span><strong data-budget-month-meals>{meals:g}食</strong></div>
<div class="budget-result"><span>30日分に必要な箱数</span><strong data-budget-boxes>{boxes}箱</strong></div>
<div class="budget-result"><span>箱単位で買う支払総額</span><strong data-budget-payment>¥{payment:,.0f}</strong></div>
<div class="budget-result"><span>30日後の未使用分（目安）</span><strong data-budget-left>{left:g}食</strong></div>
<div class="budget-result"><span>選んだ商品の1食単価</span><strong data-budget-unit>¥{unit:,.0f}</strong></div>
</div>
<p class="budget-note">30日を1か月として計算。必要食数が24の倍数でないときは箱数を切り上げます。すでに家にある在庫・消費期限・味の好みは考慮していません。商品の価格は取得時点の税込参考価格で、地域別追加送料・クーポン・ポイントは含みません。実際の購入条件は楽天の商品ページで確認してください。</p>
<p class="budget-to-products"><a href="#pack-rice-24-products">掲載商品の価格と販売先を見る →</a></p>
<noscript><p class="budget-note">数値を変更して再計算するにはJavaScriptが必要です。表示している結果は1日1食の場合です。</p></noscript>
</section>""".format(
        options="".join(choices), days=baseline["days_per_box"],
        meals=baseline["monthly_meals"], boxes=baseline["boxes"],
        payment=baseline["total_payment"], left=baseline["remaining_meals"],
        unit=baseline["per_meal"])


BUDGET_CSS = (Path(__file__).with_name("pack_rice_budget.css")
              .read_text(encoding="utf-8"))
BUDGET_JS = (Path(__file__).with_name("pack_rice_budget.js")
             .read_text(encoding="utf-8"))
