import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import (
    CATEGORIES,
    bucket,
    category_insights_html,
    item_badges,
    parse_quantity,
    shopping_bucket,
    yen,
)


class WaterShoppingVolumeLabelTests(unittest.TestCase):
    def make_item(self, single_ml, count, per_liter):
        name = f"強炭酸水 {single_ml}ml×{count}本"
        quantity = parse_quantity(name, "carbonated-water")
        self.assertIsNotNone(quantity)
        total_liters = single_ml * count / 1000
        return {
            "quantity": quantity,
            "postage_included": True,
            "price": round(total_liters * per_liter),
            "unit_prices": {
                "per_liter": per_liter,
                "per_bottle": per_liter * single_ml / 1000,
            },
        }

    def test_48_small_bottles_are_not_labeled_small_purchase(self):
        # Regression: 500ml x 48 (24L) was called small on 2026-11-20.
        large_bundle = self.make_item(500, 48, 85)
        self.assertEqual(bucket(large_bundle, "carbonated-water"), "small")
        self.assertEqual(shopping_bucket(large_bundle, "carbonated-water"), "large")
        badges = item_badges(large_bundle, self.carbonated_category(), 6)
        self.assertIn("合計12L超", badges)
        self.assertNotIn("少量向き", badges)

    def test_24_bottles_and_large_single_bottles_use_total_volume(self):
        small_bundle = self.make_item(500, 24, 100)
        large_single_bottles = self.make_item(1000, 15, 130)
        self.assertIn("合計12L以下", item_badges(small_bundle, self.carbonated_category(), 4))
        self.assertIn("合計12L超", item_badges(large_single_bottles, self.carbonated_category(), 2))
        self.assertEqual(bucket(small_bundle, "carbonated-water"), "small")
        self.assertEqual(bucket(large_single_bottles, "carbonated-water"), "large")

    def test_bulk_summary_includes_48_small_bottles(self):
        items = [
            self.make_item(500, 24, 100),
            self.make_item(500, 48, 85),
            self.make_item(1000, 15, 130),
        ]
        markup = category_insights_html(self.carbonated_category(), items)
        self.assertIn("合計12L超の注目", markup)
        self.assertIn(f"<strong>{yen(85)}</strong>", markup)

    def test_non_water_badges_keep_existing_behavior(self):
        category = next(c for c in CATEGORIES if c["id"] == "rice")
        item = {"postage_included": True, "quantity": {"total_weight_g": 5000}}
        self.assertIn("少量向き", item_badges(item, category, 4))
        item["quantity"]["total_weight_g"] = 10000
        self.assertIn("まとめ買い向き", item_badges(item, category, 4))

    @staticmethod
    def carbonated_category():
        return next(c for c in CATEGORIES if c["id"] == "carbonated-water")


if __name__ == "__main__":
    unittest.main()
