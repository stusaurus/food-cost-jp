import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from pack_rice_planner import calculation, render_planner
from build_site import AUTO_GUIDE_RULES, CATEGORIES, category_guide_navigation, guide_page


NOW = datetime(2026, 11, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def offer(i, *, price=3600, grams=180, count=24, url=None):
    return {
        "id": f"shop:item{i}",
        "name": f"パックご飯{grams}g×{count}食 商品{i}",
        "quantity": {"count": count, "unit_weight_g": grams, "total_weight_g": grams * count},
        "price": price,
        "unit_prices": {"per_serving": price / count, "per_100g": price / (count * grams / 100)},
        "postage_included": True,
        "shipping_status": "included",
        "url": url or f"https://item.rakuten.co.jp/example/pack-rice-{i}/",
        "shop": "確認済みショップ",
        "raw_name": "仕入れ元データ",
        "image": "",
        "promotion_mentioned": False,
    }


class PlannerTests(unittest.TestCase):
    def test_24_meals_one_per_day_requires_two_boxes(self):
        data = calculation(24, 3600, 1)
        self.assertEqual(data["days_per_box"], 24)
        self.assertEqual(data["boxes"], 2)
        self.assertEqual(data["purchase_total"], 7200)
        self.assertEqual(data["remaining_meals"], 18)
        self.assertEqual(data["consumption_cost"], 4500)

    def test_two_per_day_or_three_per_day_never_rounds_boxes_down(self):
        d2 = calculation(24, 3600, 2)
        self.assertEqual((d2["days_per_box"], d2["boxes"], d2["remaining_meals"]), (12, 3, 12))
        d3 = calculation(24, 3600, 3)
        self.assertEqual((d3["days_per_box"], d3["boxes"], d3["remaining_meals"]), (8, 4, 6))

    def test_invalid_inputs_rejected(self):
        for count, price, usage in [(0, 100, 1), (24, 0, 1), (24, 100, 0),
                                    (24, 100, 25), (24, -10, 2)]:
            with self.subTest(count=count, price=price, usage=usage):
                with self.assertRaises(ValueError):
                    calculation(count, price, usage)

    def test_only_verified_24_meal_rakuten_offers_appear(self):
        items = [
            offer(1),
            offer(2, price=3840, grams=200),
            offer(3, url="https://example.com/not-rakuten/"),
            offer(4, count=40),
            offer(5, url="http://item.rakuten.co.jp/not-https/"),
            {**offer(6), "postage_included": False},
        ]
        page = render_planner(items, NOW)
        self.assertIn('id="pack-rice-planner"', page)
        self.assertEqual(page.count("<option"), 2)
        self.assertIn('data-price="3600" data-count="24"', page)
        self.assertIn('data-price="3840" data-count="24"', page)
        self.assertNotIn("not-rakuten", page)
        self.assertNotIn("not-https", page)
        self.assertIn('rel="nofollow sponsored noopener"', page)
        self.assertIn("必要な購入箱数", page)
        self.assertIn("1か月は30日", page)
        self.assertIn("1食あたりの価格", page)
        self.assertIn('data-rice-stock-input', page)
        self.assertIn('data-rice-shortage', page)
        self.assertIn('data-rice-recommendation', page)
        self.assertIn("24食のパックご飯、うちでは何日持つ？", page)

    def test_one_tap_meal_choices_only_inside_verified_planner(self):
        page = render_planner([offer(1)], NOW)
        for n in (1, 2, 3, 4):
            self.assertIn(f'data-rice-meal-choice="{n}"', page)
            self.assertIn(f'{n}食/日', page)
        self.assertEqual(page.count('data-rice-meal-choice="'), 4)
        self.assertIn('aria-pressed="true"', page)
        self.assertIn('id="rice-meals-day"', page)
        self.assertIn('data-rice-stock-input', page)
        self.assertEqual(render_planner([], NOW), "")

    def test_24_pack_criteria_explain_why_best_by_meal_and_by_weight_differ(self):
        items = [
            offer(1, price=3880, grams=180),
            offer(2, price=4180, grams=200),
            offer(3, price=5436, grams=180),
        ]
        page = render_planner(items, NOW)
        self.assertIn('aria-label="24食セットの価格比較基準"', page)
        self.assertIn("1食あたりの支払額が最も低い", page)
        self.assertIn("100gに換算した単価が最も低い", page)
        self.assertIn("¥161.7／食", page)
        self.assertIn("¥87.1／100g", page)
        self.assertIn("1食180g・24食箱 ¥3,880", page)
        self.assertIn("1食200g・24食箱 ¥4,180", page)
        self.assertIn("1食単価と100g単価で最安の24食セットが異なります", page)
        self.assertEqual(page.count('<div class="rice-planner-criterion">'), 2)
        # The original ranking and affiliate link remain unchanged.
        self.assertLess(page.index('data-product-id="shop:item1"'), page.index('data-product-id="shop:item2"'))
        self.assertIn('data-position="usage_planner"', page)
        self.assertLess(page.index('class="rice-planner-criteria"'), page.index('data-rice-planner-product'))

    def test_24_pack_criteria_reject_unverified_cheaper_offer(self):
        eligible = offer(1, price=3880, grams=180)
        reference_only = {**offer(2, price=240, grams=200), "postage_included": False}
        wrong_product = offer(3, price=100, grams=200, count=40)
        page = render_planner([eligible, reference_only, wrong_product], NOW)
        self.assertIn("掲載商品の中では同じ24食セットが両基準で最安です", page)
        self.assertIn("¥161.7／食", page)
        self.assertNotIn("¥1.0／100g", page)
        self.assertNotIn("¥240", page)
        self.assertNotIn("¥100", page)
        self.assertEqual(page.count("<option"), 1)

    def test_24_pack_guide_link_first_only_if_published(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        guides = [s for s in AUTO_GUIDE_RULES if s["category_id"] == "pack-rice"]
        guide = next(s for s in guides if s["slug"] == "pack-rice-24-servings-cost")
        if len(guides) > 6:
            guides = guides[:6]
        self.assertIn(guide, guides)
        markup = category_guide_navigation(category, guides)
        first_link = markup.index('class="intent-card"')
        self.assertIn('href="../../guides/pack-rice-24-servings-cost/"', markup[first_link:first_link+130])
        without = category_guide_navigation(category, [s for s in guides if s != guide])
        self.assertNotIn('href="../../guides/pack-rice-24-servings-cost/"', without)
        self.assertNotIn("24食セットの比較ページでは", without)

    def test_empty_inventory_renders_no_planner(self):
        self.assertEqual(render_planner([], NOW), "")
        self.assertEqual(render_planner([offer(1, count=40)], NOW), "")

    def test_only_24_meal_guide_contains_planner_and_keeps_existing_seo(self):
        spec = next(x for x in AUTO_GUIDE_RULES if x["slug"] == "pack-rice-24-servings-cost")
        category = next(x for x in CATEGORIES if x["id"] == "pack-rice")
        items = [offer(1), offer(2, price=3840, grams=200), offer(3, price=4200)]
        page = guide_page(spec, category, items, NOW)
        self.assertEqual(page.count('id="pack-rice-planner"'), 1)
        self.assertLess(page.index('id="pack-rice-planner"'), page.index('<section class="section podium-section">'))
        self.assertIn('<title>パックご飯24食のコスパ比較｜必要箱数と1食・100g単価｜食品コスパ比較</title>', page)
        self.assertIn('<meta name="robots" content="index,follow">', page)
        self.assertIn('href="../../assets/pack-rice-planner.css"', page)
        self.assertIn('src="../../assets/pack-rice-planner.js"', page)
        self.assertIn('data-affiliate="rakuten"', page)
        self.assertIn('data-position="usage_planner"', page)
        self.assertIn("送料込み TOP3", page)
        self.assertIn("1食 180g", page)
        self.assertIn("1食 200g", page)
        self.assertEqual(page.count('rel="canonical"'), 1)
        self.assertEqual(page.count("<h1"), 1)

        unrelated = next(x for x in CATEGORIES if x["id"] == "rice")
        spec_other = next(x for x in AUTO_GUIDE_RULES if x["category_id"] == "rice")
        other = guide_page(spec_other, unrelated, [], NOW)
        self.assertNotIn("pack-rice-planner.js", other)
        self.assertNotIn('id="pack-rice-planner"', other)


    def test_24_meal_meta_describes_existing_planner_only(self):
        spec = next(x for x in AUTO_GUIDE_RULES if x["slug"] == "pack-rice-24-servings-cost")
        category = next(x for x in CATEGORIES if x["id"] == "pack-rice")
        page = guide_page(spec, category, [offer(1), offer(2), offer(3)], NOW)
        self.assertIn(f'<meta name="description" content="{spec["description"]}">', page)
        self.assertIn(f'<p class="lead">{spec["intro"]}</p>', page)
        self.assertIn('<h1>パックご飯24食の1食・100g単価と必要箱数を比較</h1>', page)
        self.assertIn('30日分の必要箱数を計算', page)
        self.assertIn('確認済み商品がある場合は購入総額も確認できます。', page)
        self.assertIn('id="pack-rice-planner"', page)
        self.assertIn('data-rice-stock-input', page)
        self.assertIn('rel="canonical"', page)
        self.assertEqual(page.count('<meta name="description"'), 1)
        self.assertEqual(page.count('<h1'), 1)

        # Guide metadata must remain accurate even when offers are temporarily absent.
        without_offers = guide_page(spec, category, [], NOW)
        self.assertIn(f'<meta name="description" content="{spec["description"]}">', without_offers)
        self.assertNotIn('id="pack-rice-planner"', without_offers)
        self.assertIn('data-rice-quantity-only', without_offers)
        self.assertIn('<h1>パックご飯24食の1食・100g単価と必要箱数を比較</h1>', without_offers)
        self.assertIn('確認済み商品がある場合は購入総額も確認できます。', without_offers)

        # Other guides still derive their description from their published intro.
        rice = next(x for x in CATEGORIES if x["id"] == "rice")
        other_spec = next(x for x in AUTO_GUIDE_RULES if x["category_id"] == "rice")
        other_page = guide_page(other_spec, rice, [], NOW)
        self.assertIn(f'<meta name="description" content="{other_spec["intro"]}">', other_page)
        self.assertNotIn("パックご飯24食は何箱必要", other_page)


if __name__ == "__main__":
    unittest.main()
