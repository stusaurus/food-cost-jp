import unittest
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from yahoo_pack_rice_probe import (PRODUCTS, summarize, rakuten_candidates, report,
                                  title_candidate, exact_sato_rakuten, exact_sato_yahoo, price_pair_preview, affiliate_probe)

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

    def test_price_preview_requires_fresh_exact_tax_inclusive_shipping_conditions(self):
        p = PRODUCTS[1]
        name = "サトウのごはん 銀シャリ (200g×5食)×16袋"
        row = {"id":"likaman:10040020","name":name,"price":16300,
               "shipping_status":"included","postage_included":True,
               "quantity":{"unit_weight_g":200,"count":80,"total_weight_g":16000,"component_counts":[5,16]},
               "url":"https://hb.afl.rakuten.co.jp/hgc/test/?" + urlencode({"pc":"https://item.rakuten.co.jp/likaman/950871-16/"})}
        hit = {"code":"likaman_950871-16","janCode":p[1],"name":name,
               "condition":"new","inStock":True,"shipping":{"code":2,"name":"送料無料"},
               "price":16000,"priceLabel":{"taxable":True},"url":"https://store.shopping.yahoo.co.jp/likaman/950871-16.html"}
        now = datetime(2026,11,26,12,tzinfo=timezone.utc)
        stamp = (now-timedelta(hours=2)).isoformat()
        result = price_pair_preview([row],[hit],p,stamp,now)
        self.assertEqual(result["status"],"API_PRICE_PREVIEW_ONLY")
        self.assertEqual(result["listed_price_difference_yen"],300)
        self.assertEqual(result["yahoo_per_serving_yen"],200)
        self.assertFalse(result["publish_allowed"])
        self.assertFalse(result["checkout_total_verified"])
        self.assertEqual(price_pair_preview([row],[hit],p,(now-timedelta(hours=49)).isoformat(),now)["reason"],"STALE_OR_INVALID_RAKUTEN_TIMESTAMP")
        self.assertEqual(price_pair_preview([row],[dict(hit,priceLabel={"taxable":False})],p,stamp,now)["reason"],"NEW_OR_TAX_INCLUSIVE_UNVERIFIED")
        self.assertEqual(price_pair_preview([row],[dict(hit,description="北海道・沖縄は別途送料")],p,stamp,now)["reason"],"SHIPPING_CONDITIONS_REQUIRE_REVIEW")
        self.assertEqual(price_pair_preview([dict(row,raw_name=name+" 北海道は別途送料")],[hit],p,stamp,now)["reason"],"SHIPPING_CONDITIONS_REQUIRE_REVIEW")
        self.assertEqual(price_pair_preview([row],[hit,hit],p,stamp,now)["status"],"NOT_COMPARABLE")

    def test_affiliate_validation_requires_correct_ids_and_target(self):
        p = PRODUCTS[1]
        base = "https://ck.jp.ap.valuecommerce.com/servlet/referral"
        config = base + "?sid=123&pid=456&vc_url="
        target = "https://store.shopping.yahoo.co.jp/likaman/950871-16.html"
        def ad(sid="123", pid="456", dest=target):
            return base + "?" + urlencode({"sid":sid,"pid":pid,"vc_url":dest})
        hit = {"code":"likaman_950871-16","janCode":p[1],
               "name":"サトウ 銀シャリ 200g×5食×16袋","price":16100,
               "inStock":True,"shipping":{"code":2},"url":ad()}
        def request(jan, key, affiliate_prefix=None):
            self.assertEqual(jan,p[1])
            self.assertEqual(affiliate_prefix,config)
            return [hit]
        self.assertEqual(affiliate_probe("test-client",config,request),
                         {"status":"VERIFIED","verified_food_ad_links":1,"publish_allowed":False})
        for url in (ad(sid="999"),ad(pid="999"),ad(dest=target.replace("-16","-8")),
                    ad(dest="https://example.org/"),target,
                    ad(dest=target+"?secret=test-client"),ad()+"&sid=123"):
            result = affiliate_probe("test-client",config,
                                     lambda *args, **kwargs: [dict(hit,url=url)])
            self.assertEqual(result["status"],"NOT_VERIFIED")
            self.assertFalse(result["publish_allowed"])
        self.assertEqual(affiliate_probe("test-client","",request)["status"],"NOT_CONFIGURED")
        self.assertEqual(affiliate_probe("test-client","https://example.org/",request)["status"],"NOT_VERIFIED")
        self.assertEqual(affiliate_probe("test-client",config,
                         lambda *args, **kwargs: [hit,hit])["status"],"NOT_VERIFIED")
