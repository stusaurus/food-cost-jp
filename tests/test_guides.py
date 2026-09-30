import sys
from datetime import datetime
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import (
    CATEGORIES,
    GUIDE_SPECS,
    guide_filter_items,
    guide_page,
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
        self.assertIn("楽天で確認する →", html)


if __name__ == "__main__":
    unittest.main()
