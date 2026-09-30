import sys
from datetime import date
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from price_history import apply_price_history, load_price_history, save_price_history
from build_site import (
    CATEGORIES,
    deals_page,
    price_signal,
    product_brand,
    product_identity_html,
    sparkline_svg,
    today_deals_html,
)


def category(category_id):
    return next(c for c in CATEGORIES if c["id"] == category_id)


def rice_item(price=3000, grams=5000, item_id="shop:rice-1"):
    return {
        "id": item_id,
        "raw_name": "raw",
        "name": "アイリスオーヤマ 国産米 5kg",
        "price": price,
        "shop": "テストショップ",
        "url": "https://example.com/rice",
        "image": "",
        "postage_included": True,
        "shipping_status": "included",
        "quantity": {
            "unit_weight_g": grams,
            "count": 1,
            "total_weight_g": grams,
        },
        "unit_prices": {"per_kg": price / (grams / 1000)},
        "promotion_mentioned": False,
    }


class PriceHistoryTests(unittest.TestCase):
    def test_first_observation_is_not_a_fake_price_drop(self):
        history = {"version": 1, "products": {}}
        item = rice_item(3000)
        apply_price_history(history, category("rice"), [item], date(2026, 9, 30))
        info = item["price_history"]
        self.assertEqual(info["observed_days"], 1)
        self.assertIsNone(info["previous_price"])
        self.assertIsNone(info["price_delta"])
        self.assertFalse(info["is_30d_low"])

    def test_next_day_drop_and_30_day_low_are_detected(self):
        history = {"version": 1, "products": {}}
        first = rice_item(3000)
        apply_price_history(history, category("rice"), [first], date(2026, 9, 30))

        second = rice_item(2500)
        apply_price_history(history, category("rice"), [second], date(2026, 10, 1))
        info = second["price_history"]
        self.assertEqual(info["previous_price"], 3000)
        self.assertEqual(info["price_delta"], -500)
        self.assertEqual(info["previous_label"], "昨日比")
        self.assertTrue(info["is_30d_low"])
        self.assertEqual(len(info["series_30d"]), 2)
        self.assertAlmostEqual(info["percent_delta"], -16.6666666, places=4)

    def test_quantity_change_resets_comparison(self):
        history = {"version": 1, "products": {}}
        first = rice_item(3000, grams=5000)
        apply_price_history(history, category("rice"), [first], date(2026, 9, 30))

        changed = rice_item(4900, grams=10000)
        apply_price_history(history, category("rice"), [changed], date(2026, 10, 1))
        self.assertIsNone(changed["price_history"]["previous_price"])
        self.assertIsNone(changed["price_history"]["price_delta"])

    def test_history_round_trip(self):
        history = {"version": 1, "products": {}}
        item = rice_item()
        apply_price_history(history, category("rice"), [item], date(2026, 9, 30))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "price-history.json"
            save_price_history(history, path)
            loaded = load_price_history(path)
        self.assertEqual(loaded["version"], 1)
        self.assertTrue(loaded["products"])

    def test_today_deals_only_shows_actual_drop(self):
        history = {"version": 1, "products": {}}
        first = rice_item(3000)
        apply_price_history(history, category("rice"), [first], date(2026, 9, 30))
        no_deal_html = today_deals_html({"rice": ([first], [])})
        self.assertIn("価格履歴を蓄積中", no_deal_html)
        self.assertNotIn("昨日比 ¥", no_deal_html)

        second = rice_item(2500)
        apply_price_history(history, category("rice"), [second], date(2026, 10, 1))
        deal_html = today_deals_html({"rice": ([second], [])})
        self.assertIn("今日のお買い得", deal_html)
        self.assertIn("昨日比 ¥500安い", deal_html)
        self.assertIn("30日最安", deal_html)

    def test_product_identity_separates_brand_and_quantity(self):
        item = rice_item()
        self.assertEqual(product_brand(item["name"]), "アイリスオーヤマ")
        rendered = product_identity_html(item, category("rice"))
        self.assertIn("brand-chip", rendered)
        self.assertIn("アイリスオーヤマ", rendered)
        self.assertIn("合計5kg", rendered)
        self.assertIn("spec-chip", rendered)


    def test_price_signal_and_sparkline_use_observed_history(self):
        history = {"version": 1, "products": {}}
        first = rice_item(3000)
        apply_price_history(history, category("rice"), [first], date(2026, 9, 30))
        self.assertEqual(price_signal(first)[0], "履歴蓄積中")
        self.assertIn("履歴を蓄積中", sparkline_svg(first))

        second = rice_item(2500)
        apply_price_history(history, category("rice"), [second], date(2026, 10, 1))
        label, tone, reason = price_signal(second)
        self.assertEqual(label, "買い時寄り")
        self.assertEqual(tone, "buy")
        self.assertIn("30日内の最安水準", reason)
        graph = sparkline_svg(second)
        self.assertIn("<polyline", graph)
        self.assertIn("30日価格推移", graph)

    def test_deals_page_only_collects_real_price_drops(self):
        history = {"version": 1, "products": {}}
        first = rice_item(3000)
        apply_price_history(history, category("rice"), [first], date(2026, 9, 30))
        second = rice_item(2500)
        apply_price_history(history, category("rice"), [second], date(2026, 10, 1))
        results = {c["id"]: ([], []) for c in CATEGORIES}
        results["rice"] = ([second], [])
        rendered = deals_page(
            results,
            __import__("datetime").datetime(2026, 10, 1, 7, 0),
        )
        self.assertIn("今日のお買い得だけを見る", rendered)
        self.assertIn("実際に値下がりした商品 1件", rendered)
        self.assertIn("昨日比 ¥500安い", rendered)
        self.assertIn("買い時寄り", rendered)
        self.assertIn("未来の価格を予測するものではありません", rendered)


if __name__ == "__main__":
    unittest.main()
