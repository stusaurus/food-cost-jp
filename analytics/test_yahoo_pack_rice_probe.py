import unittest
from urllib.parse import urlencode
from yahoo_pack_rice_probe import (PRODUCTS, summarize, rakuten_candidates, report,
                                  title_candidate, exact_sato_rakuten, exact_sato_yahoo)

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

    def test_iris_case_title_from_verified_listing(self):
        p = PRODUCTS[0]
        self.assertTrue(title_candidate("低温製法米のおいしいごはん パックご飯180g (1ケース24食入) アイリスフーズ", p))
        self.assertFalse(title_candidate("アイリス 低温製法米 180g (1ケース48食入)", p))
        self.assertFalse(title_candidate("アイリス 低温製法米 180g (1ケース240食入)", p))

    def test_sato_requires_exact_merchant_identity_and_quantities(self):
        p = PRODUCTS[1]
        name = "サトウのごはん 銀シャリ 5食パック (200g×5食)×16袋入"
        def link(target):
            return "https://hb.afl.rakuten.co.jp/hgc/test/?" + urlencode({"pc": target})
        row = {"id":"likaman:10040020", "name":name, "price":16300,
               "shipping_status":"included", "postage_included":True,
               "quantity":{"unit_weight_g":200,"count":80,"total_weight_g":16000,"component_counts":[5,16]},
               "url":link("https://item.rakuten.co.jp/likaman/950871-16/")}
        self.assertTrue(exact_sato_rakuten([row], p))
        self.assertFalse(exact_sato_rakuten([dict(row, id="another:10040020")], p))
        self.assertFalse(exact_sato_rakuten([dict(row, url=link("https://item.rakuten.co.jp/likaman/950871-8/"))], p))
        self.assertFalse(exact_sato_rakuten([dict(row, quantity=dict(row["quantity"],component_counts=[80]))], p))
        self.assertFalse(exact_sato_rakuten([dict(row, shipping_status="unknown")], p))
        hit = {"code":"likaman_950871-16","janCode":p[1],"name":name,"inStock":True,
               "shipping":{"code":2},"price":16000,"url":"https://store.shopping.yahoo.co.jp/likaman/950871-16.html"}
        self.assertTrue(exact_sato_yahoo([hit],p))
        for changes in ({"code":"another_950871-16"}, {"url":"https://store.shopping.yahoo.co.jp/likaman/950871-8.html"},
                        {"shipping":{"code":3}}, {"janCode":"wrong"}, {"inStock":False}, {"price":True},
                        {"name":"サトウ 銀シャリ 200g×5食×8袋"}):
            self.assertFalse(exact_sato_yahoo([dict(hit,**changes)],p))
