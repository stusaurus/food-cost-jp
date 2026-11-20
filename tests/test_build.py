import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from datetime import datetime
from build_site import CATEGORIES, category_page, faq_html, faq_json_ld, guide_faq, normalize_item, parse_quantity, unit_prices

class UnitTests(unittest.TestCase):
    def test_pack_rice(self):
        q = parse_quantity("パックご飯 200g×24食 送料無料", "pack-rice")
        self.assertEqual(q["count"], 24)
        self.assertAlmostEqual(unit_prices(3980, q, "pack-rice")["per_serving"], 3980 / 24)

    def test_regional_shipping_conditions_override_included_flag(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        for suffix, included in [
            ("送料無料※沖縄・離島別途", False),
            ("北海道は別途700円", False),
            ("四国・九州への配送は+400円", False),
            ("北海道産 送料無料", True),
        ]:
            with self.subTest(suffix=suffix):
                raw = dict(itemName="パックご飯 180g×24食 " + suffix, itemPrice=4000,
                           itemCode="shop:1", itemUrl="https://item.rakuten.co.jp/shop/1/",
                           postageFlag=0)
                item = normalize_item(raw, category)
                self.assertEqual(item["postage_included"], included)

    def test_category_page_explains_regional_shipping_rule(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        page = category_page(category, [], [], datetime(2026, 11, 20))
        self.assertIn("商品名に明記された地域別追加送料", page)
        self.assertIn("送料フラグが「込み」でも「送料別・要確認」", page)
        self.assertIn("最終支払額と在庫は販売店で確認", page)
        self.assertNotIn("送料込みは楽天APIの送料フラグを基準にし", page)

    def test_guide_shipping_faq_matches_product_classification(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        faqs = guide_faq({"title": "パックご飯24食"}, category)
        answer = next(answer for question, answer in faqs if "送料はランキング" in question)
        self.assertIn("楽天APIの送料フラグが「込み」", answer)
        self.assertIn("地域別追加送料や送料無料の対象外地域", answer)
        self.assertIn("送料別・要確認", answer)
        self.assertIn("最終支払額と在庫は販売店で確認", answer)
        self.assertNotIn("楽天APIで送料込みと確認できる商品を対象", answer)
        self.assertIn("送料無料の対象外地域", faq_html(faqs))
        self.assertIn("送料無料の対象外地域", faq_json_ld(faqs))

    def test_rice(self):
        q = parse_quantity("国産米 5kg×2袋 送料無料", "rice")
        self.assertEqual(q["total_weight_g"], 10000)
        self.assertAlmostEqual(unit_prices(4980, q, "rice")["per_kg"], 498)

    def test_water(self):
        q = parse_quantity("強炭酸水 500ml×48本 送料無料", "carbonated-water")
        self.assertEqual(q["total_volume_ml"], 24000)
        self.assertEqual(unit_prices(2880, q, "carbonated-water")["per_bottle"], 60)

    def test_selectable_rejected(self):
        self.assertIsNone(parse_quantity("白米 選べる 5kg 10kg", "rice"))

if __name__ == "__main__":
    unittest.main()
