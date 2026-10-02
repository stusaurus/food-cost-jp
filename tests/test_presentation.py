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
        "name": f"テスト商品 {rank}",
        "price": 2400 + rank,
        "shop": "テストショップ",
        "url": f"https://example.com/item-{rank}",
        "image": "https://example.com/image.jpg",
        "postage_included": True,
        "shipping_status": "included",
        "promotion_mentioned": False,
    }
    if category_id == "pack-rice":
        count = 24 if rank % 2 else 40
        base["name"] = f"テスト パックご飯 200g×{count}食"
        base["quantity"] = {"unit_weight_g": 200, "count": count, "total_weight_g": 200 * count}
        base["unit_prices"] = {"per_serving": 90 + rank * 10, "per_100g": 45 + rank * 5}
    elif category_id == "rice":
        grams = 5000 if rank % 2 else 10000
        base["name"] = f"テスト米 {grams/1000:g}kg"
        base["quantity"] = {"unit_weight_g": grams, "count": 1, "total_weight_g": grams}
        base["unit_prices"] = {"per_kg": 470 + rank * 10}
    elif category_id == "carbonated-water":
        ml = 500 if rank % 2 else 1000
        base["name"] = f"テスト炭酸水 {ml}ml×24本"
        base["quantity"] = {"unit_volume_ml": ml, "count": 24, "total_volume_ml": ml * 24}
        base["unit_prices"] = {"per_liter": 190 + rank * 10, "per_bottle": 90 + rank * 10}
    else:
        grams = 1000 if rank % 2 else 2000
        base["name"] = f"テスト オートミール {grams/1000:g}kg"
        base["quantity"] = {"unit_weight_g": grams, "count": 1, "total_weight_g": grams}
        base["unit_prices"] = {"per_100g": 230 + rank * 10, "per_kg": 2300 + rank * 100}
    return base


NOW = datetime(2026, 9, 30, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


class PresentationTests(unittest.TestCase):
    def test_mobile_card_css_exists(self):
        self.assertIn('@media(max-width:759px)', CSS)
        self.assertIn('td[data-cell="cta"]', CSS)
        self.assertIn('.rank.top', CSS)
        self.assertIn('.finder-products', CSS)
        self.assertIn('.more-products', CSS)
        self.assertIn('.start-grid', CSS)
        self.assertIn('.service-shortcuts', CSS)
        self.assertIn('.product-extra', CSS)
        self.assertIn('.journey-strip', CSS)

    def test_category_page_has_top3_and_collapsed_rest(self):
        category = next(c for c in CATEGORIES if c["id"] == "carbonated-water")
        items = [sample_item("carbonated-water", i) for i in range(1, 6)]
        html = category_page(category, items, [], NOW)
        self.assertIn("送料込み最安", html)
        self.assertIn("送料込み TOP3", html)
        self.assertIn("4位以下を見る（2件）", html)
        self.assertIn('class="more-products"', html)
        self.assertIn('<span class="rank">4</span>', html)
        self.assertIn("600ml以下", html)
        self.assertIn("700ml以上", html)
        self.assertIn("商品名・ショップ名で絞る", html)
        self.assertIn("炭酸水を比べるコツ", html)
        self.assertIn('class="guide-mascot compact"', html)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertIn('"@type": "ItemList"', html)
        self.assertIn("よくある質問", html)
        self.assertIn("PRICE SNAPSHOT", html)
        self.assertIn("1位と3位の差", html)
        self.assertIn('data-save-product', html)
        self.assertIn('data-compare-product', html)
        self.assertIn('data-compare-bar', html)
        self.assertIn('data-open-saved', html)
        self.assertIn("候補を見る", html)
        self.assertIn("比較する", html)
        self.assertIn("あとで見る", html)
        self.assertIn("../../deals/", html)
        self.assertIn("../../saved/", html)
        self.assertIn('data-product-extra', html)
        self.assertIn('data-start-rank="4"', html)
        self.assertIn("const base=Number(root.dataset.startRank||1)", html)

    def test_home_has_mascot_and_guided_finder(self):
        results = {
            category["id"]: ([sample_item(category["id"], i) for i in range(1, 5)], [])
            for category in CATEGORIES
        }
        html = home_page(results, NOW)
        self.assertIn("送料込み 4件を比較中", html)
        self.assertIn("この売り場へ →", html)
        self.assertIn("毎日の食品を、賢く選ぶ小さなマルシェ", html)
        self.assertIn("今日の買い物を、", html)
        self.assertIn('class="hero-visual"', html)
        self.assertIn('assets/marche-hero.webp', html)
        self.assertIn("単価と送料をそろえて", html)
        self.assertIn("今日は、どう探す？", html)
        self.assertIn('data-finder-category="rice"', html)
        self.assertIn('data-entry-route="deal"', html)
        self.assertIn('data-finder-category-stage hidden', html)
        self.assertIn('data-finder-result-stage hidden', html)
        self.assertIn('data-save-product', html)
        self.assertIn('data-open-saved', html)
        self.assertIn("food_cost_saved_v1", html)
        self.assertIn("food_cost_compare_v1", html)
        self.assertIn("product_compare_add", html)
        self.assertIn("本日のおすすめ棚", html)
        self.assertIn('data-start-route="deals"', html)
        self.assertIn('data-start-route="finder"', html)
        self.assertIn('data-start-route="categories"', html)
        self.assertIn('id="quick-finder"', html)
        self.assertIn('id="categories"', html)
        self.assertIn("今日のお買い得", html)
        self.assertIn("買い物メモ", html)
        self.assertIn("home_start_route", html)
        self.assertIn("product_detail_open", html)

    def test_finder_embeds_real_product_recommendations(self):
        results = {
            category["id"]: ([sample_item(category["id"], i) for i in range(1, 5)], [])
            for category in CATEGORIES
        }
        html = home_page(results, NOW)
        self.assertIn('data-finder-picks="rice:cheap"', html)
        self.assertIn('data-finder-picks="rice:small"', html)
        self.assertIn('data-finder-picks="rice:large"', html)
        self.assertIn('data-position="quick_finder_result"', html)
        self.assertIn('data-product-extra', html)
        self.assertIn("それなら、この棚から。", html)
        self.assertIn("この売り場の商品一覧へ →", html)
        self.assertIn("quick_finder_category", html)
        self.assertIn("quick_finder_complete", html)

    def test_finder_landing_opens_collapsed_results(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        items = [sample_item("pack-rice", i) for i in range(1, 6)]
        html = category_page(category, items, [], NOW)
        self.assertIn("quick_finder_landing", html)
        self.assertIn("details.open=true", html)
        self.assertIn("条件に合う商品がありません", html)

    def test_recommendation_badges_and_top3_difference(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        items = [sample_item("pack-rice", i) for i in range(1, 4)]
        items[0]["unit_prices"]["per_serving"] = 90
        items[1]["unit_prices"]["per_serving"] = 100
        items[2]["unit_prices"]["per_serving"] = 110
        html = category_page(category, items, [], NOW)
        self.assertIn("最安候補", html)
        self.assertIn("TOP3", html)
        self.assertIn("少量向き", html)
        self.assertIn("最安との差 +¥10.0", html)
        self.assertIn("最安との差 +¥20.0", html)

    def test_shipping_unknown_is_collapsed(self):
        category = next(c for c in CATEGORIES if c["id"] == "rice")
        included = [sample_item("rice", i) for i in range(1, 4)]
        other = [sample_item("rice", 8), sample_item("rice", 9)]
        for item in other:
            item["postage_included"] = False
            item["shipping_status"] = "extra_or_unknown"
        html = category_page(category, included, other, NOW)
        self.assertIn("送料別の参考商品を見る（2件）", html)
        self.assertIn('data-more-products', html)


if __name__ == "__main__":
    unittest.main()
