import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from marketplace_comparison import collect_pair, collect_expansion_pair, render_pair
from yahoo_pack_rice_probe import EXPANSION
from build_site import CATEGORIES, category_page
from validate_generated_site import PageAudit

class MarketplaceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.stamp = self.now.isoformat()
        self.config = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3790012&pid=456&vc_url="
        self.target = "https://store.shopping.yahoo.co.jp/likaman/950871-16.html"
        name = "サトウのごはん 銀シャリ (200g×5食)×16袋"
        self.row = {"id":"likaman:10040020","name":name,"price":16300,
                    "shipping_status":"included","postage_included":True,
                    "quantity":{"unit_weight_g":200,"count":80,"total_weight_g":16000,"component_counts":[5,16]},
                    "url":"https://hb.afl.rakuten.co.jp/hgc/test/?" + urlencode({"pc":"https://item.rakuten.co.jp/likaman/950871-16/"})}
        self.hit = {"code":"likaman_950871-16","janCode":"4973360566850","name":name,
                    "condition":"new","inStock":True,"shipping":{"code":2,"name":"送料無料"},
                    "price":16100,"priceLabel":{"taxable":True},
                    "url":"https://ck.jp.ap.valuecommerce.com/servlet/referral?" + urlencode({"sid":"3790012","pid":"456","vc_url":self.target})}

    def pair(self, hit=None, **kw):
        return collect_pair([self.row], self.stamp, "test-client", self.config, approved=True,
                            request=lambda *a,**k:[self.hit if hit is None else hit], now=self.now, **kw)

    def test_default_never_calls_api(self):
        def unexpected(*a, **k):
            self.fail("must not contact API")
        self.assertIsNone(collect_pair([self.row], self.stamp, "test-client", self.config, request=unexpected))
        self.assertEqual(render_pair(None), "")

    def test_wrong_site_id_is_rejected_before_network(self):
        def unexpected(*a, **k):
            self.fail("wrong site must not contact API")
        self.assertIsNone(collect_pair([self.row], self.stamp, "test-client",
                                      self.config.replace("3790012", "3790024"),
                                      approved=True, request=unexpected, now=self.now))

    def test_verified_pair_price_tracking_and_expiry(self):
        pair = self.pair()
        self.assertIsNotNone(pair)
        output = render_pair(pair, self.now)
        for value in ("16,300円", "16,100円", "203.75円", "201.25円", "200円安い",
                      'data-affiliate="yahoo"', 'data-affiliate="rakuten"', 'data-price-expiry=', "最終支払額"):
            self.assertIn(value, output)
        audit = PageAudit(); audit.feed(output)
        self.assertFalse(audit.affiliate_errors)
        self.assertEqual(render_pair(pair, self.now+timedelta(hours=49)), "")
        self.assertIn("同額", render_pair(replace(pair, yahoo_price=16300), self.now))
        self.assertIn("楽天市場の掲載価格が", render_pair(replace(pair, yahoo_price=16400), self.now))

    def test_wrong_destination_or_shipping_never_renders(self):
        for hit in (dict(self.hit,url=self.hit["url"].replace("pid=456","pid=789")),
                    dict(self.hit,description="北海道は別途送料"),
                    dict(self.hit,inStock=False)):
            self.assertIsNone(self.pair(hit))

    def test_category_integration_is_scoped(self):
        pair = self.pair()
        rice = next(c for c in CATEGORIES if c["id"]=="pack-rice")
        pasta = next(c for c in CATEGORIES if c["id"]=="pasta")
        self.assertIn('id="marketplace-comparison"', category_page(rice, [], [], self.now, marketplace_pair=pair))
        self.assertNotIn('id="marketplace-comparison"', category_page(rice, [], [], self.now))
        self.assertNotIn('id="marketplace-comparison"', category_page(pasta, [], [], self.now, marketplace_pair=pair))


    def test_expansion_pair_collection_render_and_fail_closed(self):
        for spec, name, jan, unit, price, unit_price in (
            (EXPANSION[0], "ディチェコ No.12 500g×24袋", "", "100g", 8980, "74.83"),
            (EXPANSION[1], "ハルナウォーター 安曇野の自然が育んだ天然水 2L×12本", "4510892001338", "1L", 1836, "76.50"),
        ):
            with self.subTest(category=spec[0]):
                store, sku = spec[3].split("_",1)
                row = dict(self.row, id=spec[1], name=name, price=price,
                           quantity={spec[8]:spec[9],spec[10]:spec[11],"count":spec[12]},
                           url="https://hb.afl.rakuten.co.jp/hgc/test/?" + urlencode({"pc":"https://item.rakuten.co.jp"+spec[2]}))
                hit = dict(self.hit, code=spec[3], name=name, janCode=jan, price=price,
                           url="https://ck.jp.ap.valuecommerce.com/servlet/referral?" + urlencode({"sid":"3790012","pid":"456","vc_url":f"https://store.shopping.yahoo.co.jp/{store}/{sku}.html"}))
                def collect(rows=None,hits=None,stamp=None):
                    return collect_expansion_pair(spec[0], [row] if rows is None else rows,
                        self.stamp if stamp is None else stamp, "test-client", self.config, approved=True,
                        request=lambda *a,**k:[hit] if hits is None else hits, now=self.now)
                pair = collect()
                self.assertIsNotNone(pair)
                output = render_pair(pair,self.now)
                self.assertIn(f"{unit} {unit_price}円",output)
                self.assertIn(f'data-category="{spec[0]}"',output)
                self.assertIn("同額",output)
                audit = PageAudit(); audit.feed(output)
                self.assertFalse(audit.affiliate_errors)
                bad = PageAudit(); bad.feed(output.replace(spec[3],"wrong_sku"))
                self.assertTrue(bad.affiliate_errors)
                category = next(c for c in CATEGORIES if c["id"] == spec[0])
                self.assertIn('id="marketplace-comparison"',category_page(category,[],[],self.now,marketplace_pair={spec[0]:pair}))
                self.assertIsNone(collect(hits=[hit,hit]))
                self.assertIsNone(collect(hits=[dict(hit, description="沖縄は別途送料")]))
                self.assertIsNone(collect(hits=[dict(hit, url=hit["url"].replace("pid=456","pid=789"))]))
                self.assertIsNone(collect(rows=[dict(row,quantity=dict(row["quantity"],count=1))]))
                self.assertIsNone(collect(stamp=(self.now-timedelta(hours=49)).isoformat()))
                if spec[0] == "mineral-water":
                    self.assertIsNone(collect(hits=[dict(hit,janCode="wrong")]))
