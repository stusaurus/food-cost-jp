import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_site import CATEGORIES, REGIONAL_POSTAGE, norm, normalize_item_with_reason


class ShippingExclusionTests(unittest.TestCase):
    def category(self):
        return next(c for c in CATEGORIES if c["id"] == "mineral-water")

    def raw(self, title):
        return {
            "itemName": title,
            "itemPrice": 4980,
            "postageFlag": 0,
            "affiliateUrl": "https://hb.afl.rakuten.co.jp/hgc/test/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fonestep%2Fs01176%2F",
            "itemCode": "onestep:s01176",
            "shopName": "よろずやマルシェ",
        }

    def test_exclusions_are_not_guaranteed_shipping_included(self):
        names = [
            "ボルヴィック 500ml 48本 軟水 天然水 ミネラルウォーター ボルビック volvic『送料無料（一部地域除く）』",
            "ミネラルウォーター 500ml×48本 送料無料 ※一部地域を除く",
            "ミネラルウォーター 500ml×48本 送料無料（北海道・沖縄を除く）",
            "ミネラルウォーター 500ml×48本 送料込み（離島対象外）",
            "ミネラルウォーター 500ml×48本 送料無料（沖縄・離島除外）",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertIsNotNone(REGIONAL_POSTAGE.search(norm(name)))
                item, reason = normalize_item_with_reason(self.raw(name), self.category())
                self.assertIsNone(reason)
                self.assertEqual(item["quantity"]["count"], 48)
                self.assertEqual(item["price"], 4980)
                self.assertEqual(item["id"], "onestep:s01176")
                self.assertEqual(item["url"], self.raw(name)["affiliateUrl"])
                self.assertFalse(item["postage_included"])
                self.assertEqual(item["shipping_status"], "extra_or_unknown")

    def test_ordinary_free_shipping_remains_included(self):
        name = "ミネラルウォーター 500ml×48本 送料無料"
        self.assertIsNone(REGIONAL_POSTAGE.search(norm(name)))
        item, reason = normalize_item_with_reason(self.raw(name), self.category())
        self.assertIsNone(reason)
        self.assertTrue(item["postage_included"])
        self.assertEqual(item["shipping_status"], "included")

    def test_existing_extra_postage_patterns_stay_excluded(self):
        for name in ("袋麺 30食 北海道は別途700円", "米10kg 九州は別途送料"):
            with self.subTest(name=name):
                self.assertIsNotNone(REGIONAL_POSTAGE.search(norm(name)))


if __name__ == "__main__":
    unittest.main()
