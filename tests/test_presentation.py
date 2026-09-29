import sys
from datetime import datetime
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import CATEGORIES, CSS, category_page, home_page


def sample_item(category_id: str, rank: int = 1):
    base = {
        "id": f"shop:item-{category_id}-{rank}",
        "raw_name": "raw",
        "name": "テスト商品 500ml×24本",
        "price": 2400,
        "shop": "テストショップ",
        "url": "https://example.com/item",
        "image": "https://example.com/image.jpg",
        "postage_included": True,
        "shipping_status": "included",
        "promotion_mentioned": False,
    }
    if category_id == "pack-rice":
        base["name"] = "テスト パックご飯 200g×24食"
        base["quantity"] = {"unit_weight_g": 200, "count": 24, "total_weight_g": 4800}
        base["unit_prices"] = {"per_serving": 100, "per_100g": 50}
    elif category_id == "rice":
        base["name"] = "テスト米 5kg"
        base["quantity"] = {"unit_weight_g": 5000, "count": 1, "total_weight_g": 5000}
        base["unit_prices"] = {"per_kg": 480}
    elif category_id == "carbonated-water":
        base["quantity"] = {"unit_volume_ml": 500, "count": 24, "total_volume_ml": 12000}
        base["unit_prices"] = {"per_liter": 200, "per_bottle": 100}
    else:
        base["name"] = "テスト オートミール 1kg"
        base["quantity"] = {"unit_weight_g": 1000, "count": 1, "total_weight_g": 1000}
        base["unit_prices"] = {"per_100g": 240, "per_kg": 2400}
    return base


class PresentationTests(unittest.TestCase):
    def test_mobile_card_css_exists(self):
        self.assertIn('@media(max-width:719px)', CSS)
        self.assertIn('td[data-cell="cta"]', CSS)
        self.assertIn('.rank.top', CSS)

    def test_category_page_has_summary_specific_filters_and_guide(self):
        category = next(c for c in CATEGORIES if c["id"] == "carbonated-water")
        html = category_page(
            category,
            [sample_item("carbonated-water")],
            [],
            datetime(2026, 9, 30, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
        self.assertIn("送料込み最安", html)
        self.assertIn("600ml以下", html)
        self.assertIn("700ml以上", html)
        self.assertIn("炭酸水を比べるコツ", html)
        self.assertIn('data-cell="unit"', html)
        self.assertIn("楽天で価格を見る →", html)
        self.assertIn("商品名・ショップ名で絞る", html)
        self.assertIn('data-search-text=', html)
        self.assertIn("ほかの食品も単価で比べる", html)
        self.assertIn("パックご飯", html)

    def test_home_page_shows_best_price_and_count(self):
        results = {}
        for category in CATEGORIES:
            results[category["id"]] = ([sample_item(category["id"])], [])
        html = home_page(
            results,
            datetime(2026, 9, 30, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
        self.assertIn("送料込み 1件を比較中", html)
        self.assertIn("ランキングを見る →", html)
        self.assertIn("毎回楽天から再取得", html)
        self.assertIn("販売数量を一意に確定できない商品はランキングから除外", html)

    def test_search_filter_tracking_is_present(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        html = category_page(
            category,
            [sample_item("pack-rice")],
            [],
            datetime(2026, 9, 30, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
        self.assertIn("comparison_search_use", html)
        self.assertIn("条件に合う商品がありません", html)


if __name__ == "__main__":
    unittest.main()
