import unittest
from yahoo_pack_rice_probe import PRODUCTS, summarize, rakuten_candidates, report

class YahooProbeTests(unittest.TestCase):
    def test_rakuten_quantity_and_product_scope(self):
        base = {"name":"アイリスフーズ 低温製法米 １８０ｇ×２４食",
                "shipping_status":"included", "quantity":{"unit_weight_g":180,"count":24}}
        self.assertEqual(rakuten_candidates([base, dict(base, shipping_status="unknown"),
                         dict(base, quantity={"unit_weight_g":200,"count":24}),
                         dict(base,name="アイリス 玄米 低温製法米 180g×24食")],PRODUCTS[0]),1)

    def test_jan_alone_is_not_quantity_match(self):
        p=PRODUCTS[1]
        base={"code":"shop_1","janCode":p[1],"name":"サトウのごはん 銀シャリ (200g×5食)×16袋",
              "inStock":True,"shipping":{"code":2}}
        hits=[base,base,dict(base,code="shop_2",name="サトウ 銀シャリ 200g×5食"),
              dict(base,code="shop_3",janCode="wrong"),
              dict(base,code="shop_4",shipping={"code":3}),
              dict(base,code="shop_5",inStock=False)]
        self.assertEqual(summarize(hits,p),{"api_hits":5,"jan_hits":4,
                         "title_quantity_candidates":2,"free_shipping_flag_candidates":1})
        self.assertEqual(report({}, "")["status"],"NOT_CONFIGURED")
