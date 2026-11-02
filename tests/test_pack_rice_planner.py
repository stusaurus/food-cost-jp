import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from pack_rice_planner import calculation, render_planner
from build_site import AUTO_GUIDE_RULES, CATEGORIES, guide_page


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
        self.assertIn("30日分の必要箱数", page)
        self.assertIn("1か月は30日", page)
        self.assertIn("1食あたりの価格", page)
        self.assertIn("24食のパックご飯、うちでは何日持つ？", page)

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
        self.assertIn('<title>パックご飯24食のコスパ比較｜食品コスパ比較</title>', page)
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


if __name__ == "__main__":
    unittest.main()
