import sys
from datetime import datetime
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import (
    AUTO_GUIDE_RULES,
    CATEGORIES,
    GUIDE_SPECS,
    eligible_auto_guides,
    guide_filter_items,
    guide_page,
    optimization_report,
)


NOW = datetime(2026, 9, 30, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def item(category_id, *, grams=0, ml=0, count=1, price=2000):
    base = {
        "id": f"shop:{category_id}:{grams}:{ml}:{count}",
        "raw_name": "raw",
        "name": f"テスト {category_id}",
        "price": price,
        "shop": "テストショップ",
        "url": "https://example.com/item",
        "image": "",
        "postage_included": True,
        "shipping_status": "included",
        "promotion_mentioned": False,
    }
    if category_id == "pack-rice":
        base["quantity"] = {"unit_weight_g": grams, "count": count, "total_weight_g": grams * count}
        base["unit_prices"] = {"per_serving": price / count, "per_100g": price / (grams * count / 100)}
    elif category_id == "rice":
        base["quantity"] = {"unit_weight_g": grams, "count": count, "total_weight_g": grams * count}
        base["unit_prices"] = {"per_kg": price / (grams * count / 1000)}
    elif category_id == "carbonated-water":
        base["quantity"] = {"unit_volume_ml": ml, "count": count, "total_volume_ml": ml * count}
        base["unit_prices"] = {"per_liter": price / (ml * count / 1000), "per_bottle": price / count}
    else:
        base["quantity"] = {"unit_weight_g": grams, "count": count, "total_weight_g": grams * count}
        base["unit_prices"] = {"per_100g": price / (grams * count / 100), "per_kg": price / (grams * count / 1000)}
    return base


class GuideTests(unittest.TestCase):
    def test_eight_search_intent_guides_exist(self):
        self.assertEqual(len(GUIDE_SPECS), 8)
        slugs = {x["slug"] for x in GUIDE_SPECS}
        self.assertIn("rice-5kg-cost", slugs)
        self.assertIn("rice-10kg-cost", slugs)
        self.assertIn("carbonated-water-24-cost", slugs)
        self.assertIn("carbonated-water-48-cost", slugs)

    def test_category_links_only_to_published_matching_guides(self):
        from build_site import category_guide_navigation
        category = next(x for x in CATEGORIES if x["id"] == "rice")
        rice = next(x for x in GUIDE_SPECS if x["slug"] == "rice-5kg-cost")
        water = next(x for x in GUIDE_SPECS if x["slug"] == "carbonated-water-24-cost")
        html = category_guide_navigation(category, [rice, water])
        self.assertIn("../../guides/rice-5kg-cost/", html)
        self.assertNotIn("carbonated-water-24-cost", html)
        self.assertNotIn("rice-10kg-cost", html)
        self.assertEqual(category_guide_navigation(category, []), "")

    def test_guide_filters_do_not_backfill_wrong_sizes(self):
        category = next(x for x in CATEGORIES if x["id"] == "rice")
        spec = next(x for x in GUIDE_SPECS if x["slug"] == "rice-5kg-cost")
        items = [item("rice", grams=10000)]
        self.assertEqual(guide_filter_items(spec, items, category), [])

    def test_guide_filters_match_target_quantity(self):
        category = next(x for x in CATEGORIES if x["id"] == "carbonated-water")
        spec = next(x for x in GUIDE_SPECS if x["slug"] == "carbonated-water-24-cost")
        items = [
            item("carbonated-water", ml=500, count=24, price=1800),
            item("carbonated-water", ml=500, count=48, price=3200),
        ]
        picked = guide_filter_items(spec, items, category)
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0]["quantity"]["count"], 24)

    def test_guide_page_has_canonical_faq_and_no_false_backfill(self):
        category = next(x for x in CATEGORIES if x["id"] == "rice")
        spec = next(x for x in GUIDE_SPECS if x["slug"] == "rice-5kg-cost")
        html = guide_page(spec, category, [item("rice", grams=10000)], NOW)
        self.assertIn("guides/rice-5kg-cost/", html)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertIn('"@type": "ItemList"', html)
        self.assertIn("よくある質問", html)
        self.assertIn('data-open-saved', html)
        self.assertIn('data-compare-bar', html)
        self.assertIn("現在、条件に一致する掲載候補はありません", html)
        self.assertIn("別サイズの商品で穴埋めせず", html)

    def test_guide_page_uses_live_matching_products(self):
        category = next(x for x in CATEGORIES if x["id"] == "oatmeal")
        spec = next(x for x in GUIDE_SPECS if x["slug"] == "oatmeal-1kg-cost")
        items = [
            item("oatmeal", grams=1000, price=1200),
            item("oatmeal", grams=1000, price=1300),
            item("oatmeal", grams=1000, price=1400),
        ]
        html = guide_page(spec, category, items, NOW)
        self.assertIn("送料込み TOP3", html)
        self.assertIn("オートミール1kg前後", html)
        self.assertIn("最安候補を楽天で確認 →", html)


    def test_auto_guides_require_three_matching_products(self):
        results = {c["id"]: ([], []) for c in CATEGORIES}
        water = [
            item("carbonated-water", ml=500, count=24, price=1800 + i * 100)
            for i in range(3)
        ]
        for i, row in enumerate(water):
            row["id"] = f"shop:water-{i}"
        results["carbonated-water"] = (water, [])
        guides = eligible_auto_guides(results)
        slugs = {g["slug"] for g in guides}
        self.assertIn("carbonated-water-500ml-24-cost", slugs)

        results["carbonated-water"] = (water[:2], [])
        slugs = {g["slug"] for g in eligible_auto_guides(results)}
        self.assertNotIn("carbonated-water-500ml-24-cost", slugs)

    def test_auto_guide_rules_are_data_backed(self):
        self.assertGreaterEqual(len(AUTO_GUIDE_RULES), 6)
        self.assertTrue(all(rule.get("auto") for rule in AUTO_GUIDE_RULES))

    def test_optimization_report_records_seo_and_analytics_plan(self):
        results = {c["id"]: ([], []) for c in CATEGORIES}
        water = [
            item("carbonated-water", ml=500, count=24, price=1800 + i * 100)
            for i in range(3)
        ]
        for i, row in enumerate(water):
            row["id"] = f"shop:water-{i}"
            row["price_history"] = {"observed_days": 2, "price_delta": None}
        results["carbonated-water"] = (water, [])
        guides = eligible_auto_guides(results)
        report = optimization_report(results, guides, NOW)
        self.assertEqual(report["auto_seo"]["minimum_products"], 3)
        self.assertGreaterEqual(report["auto_seo"]["published_count"], 1)
        self.assertIn("cta_variant", report["analytics"]["dimensions"])
        self.assertIn("click_position", report["analytics"]["dimensions"])
        self.assertTrue(report["priority_queue"])


if __name__ == "__main__":
    unittest.main()
