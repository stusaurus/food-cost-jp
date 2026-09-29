import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import CATEGORIES, normalize_item, parse_quantity
from product_display import clean_display_name
from product_quality import (
    category_rejection,
    product_fingerprint,
    quantity_conflict,
    quantity_signature,
)


class ProductDisplayTests(unittest.TestCase):
    def test_food_promotion_prefixes_are_removed(self):
        product = "アイリスオーヤマ パックご飯 180g×24食"
        prefixes = [
            "【最大1,500円OFFクーポン】",
            "【9/29限定★P5倍】",
            "＼お買い物マラソン／【ポイント10倍】",
            "送料無料！ ",
            "【楽天スーパーSALE】",
            "クーポンで300円OFF★先着順 ",
            "300円OFFクーポンあり★食いしんぼう祭 ",
        ]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(clean_display_name(prefix + product), product)

    def test_trailing_promotion_label_is_removed(self):
        self.assertEqual(
            clean_display_name("国産米 5kg【最大1000円引クーポン】"),
            "国産米 5kg",
        )

    def test_identity_and_quantity_labels_are_never_removed(self):
        titles = [
            "【サトウのごはん】200g×24食",
            "【24食セット】パックご飯 200g×24食",
            "【P5倍 200g×24食】パックご飯",
            "【1000円OFFクーポン コシヒカリ】新潟県産米 5kg",
            "【オートミール 1kg】ロールドオーツ",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assertEqual(clean_display_name(title), title)

    def test_cleanup_is_idempotent(self):
        title = "【9/29限定】【最大1000円OFFクーポン】炭酸水 500ml×24本"
        once = clean_display_name(title)
        self.assertEqual(clean_display_name(once), once)


class ProductQualityTests(unittest.TestCase):
    def test_wrong_products_are_rejected(self):
        cases = [
            ("pack-rice", "レトルトカレー 200g×24個"),
            ("rice", "米粉 5kg"),
            ("carbonated-water", "コーラ 500ml×24本"),
            ("oatmeal", "オートミールクッキー 1kg"),
        ]
        for category, title in cases:
            with self.subTest(category=category, title=title):
                self.assertIsNotNone(category_rejection(category, title))

    def test_normal_products_are_accepted(self):
        cases = [
            ("pack-rice", "パックご飯 200g×24食"),
            ("rice", "新潟県産 米 5kg 米びつ当番プレゼント"),
            ("carbonated-water", "VOX 強炭酸水 500ml 24本 コーラフレーバー ハイボール用"),
            ("oatmeal", "オートミール 2kg 製パン材料にも"),
        ]
        for category, title in cases:
            with self.subTest(category=category, title=title):
                self.assertIsNone(category_rejection(category, title))

    def test_unaccounted_outer_case_is_rejected(self):
        q = parse_quantity("パックご飯 200g×24食 2ケース", "pack-rice")
        self.assertIsNotNone(q)
        self.assertTrue(quantity_conflict("パックご飯 200g×24食 2ケース", "pack-rice", q))

        q = parse_quantity("強炭酸水 500ml×24本 2ケース", "carbonated-water")
        self.assertIsNotNone(q)
        self.assertTrue(quantity_conflict("強炭酸水 500ml×24本 2ケース", "carbonated-water", q))

    def test_repeated_same_count_is_not_a_conflict(self):
        q = parse_quantity("パックご飯 24食 200g×24食", "pack-rice")
        self.assertIsNotNone(q)
        self.assertFalse(quantity_conflict("パックご飯 24食 200g×24食", "pack-rice", q))

    def test_explicit_nested_cases_are_counted(self):
        q = parse_quantity("サトウのごはん 200g×5食×16袋 80食", "pack-rice")
        self.assertEqual(q["count"], 80)
        self.assertFalse(quantity_conflict("サトウのごはん 200g×5食×16袋 80食", "pack-rice", q))

        exact = "【80食】サトウのごはん 銀シャリ 5食パック (200g×5食)×16袋入"
        q = parse_quantity(exact, "pack-rice")
        self.assertEqual(q["count"], 80)
        self.assertFalse(quantity_conflict(exact, "pack-rice", q))

        q = parse_quantity("強炭酸水 500ml×24本×2ケース 計48本", "carbonated-water")
        self.assertEqual(q["count"], 48)
        self.assertEqual(q["total_volume_ml"], 24000)
        self.assertFalse(quantity_conflict("強炭酸水 500ml×24本×2ケース 計48本", "carbonated-water", q))

    def test_adjacent_counts_are_parsed_when_unambiguous(self):
        title = "炭酸水 500ml 48本 (24本×2ケース)"
        q = parse_quantity(title, "carbonated-water")
        self.assertEqual(q["count"], 48)
        self.assertFalse(quantity_conflict(title, "carbonated-water", q))

        q = parse_quantity("有機オートミール 1kg 3袋", "oatmeal")
        self.assertEqual(q["count"], 3)
        self.assertEqual(q["total_weight_g"], 3000)

    def test_non_quantity_choices_do_not_force_rejection(self):
        q = parse_quantity("選べるラベルレス 強炭酸水 500ml×24本", "carbonated-water")
        self.assertIsNotNone(q)
        self.assertEqual(q["count"], 24)

    def test_normalize_uses_raw_title_for_quantity_and_clean_title_for_display(self):
        category = next(c for c in CATEGORIES if c["id"] == "pack-rice")
        raw = {
            "itemName": "【最大1,500円OFFクーポン】アイリス パックご飯 180g×24食",
            "itemPrice": 3000,
            "postageFlag": 0,
            "affiliateUrl": "https://hb.afl.rakuten.co.jp/test",
            "itemCode": "shop:item",
            "shopName": "shop",
        }
        item = normalize_item(raw, category)
        self.assertIsNotNone(item)
        self.assertEqual(item["raw_name"], raw["itemName"])
        self.assertEqual(item["name"], "アイリス パックご飯 180g×24食")
        self.assertEqual(item["quantity"]["count"], 24)

    def test_quantity_signature_separates_size_variants(self):
        a = parse_quantity("強炭酸水 500ml×24本", "carbonated-water")
        b = parse_quantity("強炭酸水 1000ml×12本", "carbonated-water")
        self.assertNotEqual(
            quantity_signature("carbonated-water", a),
            quantity_signature("carbonated-water", b),
        )

    def test_fingerprint_ignores_display_punctuation_not_capacity(self):
        self.assertEqual(
            product_fingerprint("炭酸水 500ml × 24本"),
            product_fingerprint("炭酸水 500ml×24本"),
        )
        self.assertNotEqual(
            product_fingerprint("炭酸水 500ml×24本"),
            product_fingerprint("炭酸水 500ml×48本"),
        )


if __name__ == "__main__":
    unittest.main()
