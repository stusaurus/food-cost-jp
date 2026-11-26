import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from marketplace_comparison import collect_pair, render_pair
from build_site import CATEGORIES, category_page
from validate_generated_site import PageAudit

class MarketplaceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.stamp = self.now.isoformat()
        self.config = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=123&pid=456&vc_url="
        self.target = "https://store.shopping.yahoo.co.jp/likaman/950871-16.html"
        name = "サトウのごはん 銀シャリ (200g×5食)×16袋"
        self.row = {"id":"likaman:10040020","name":name,"price":16300,
                    "shipping_status":"included","postage_included":True,
                    "quantity":{"unit_weight_g":200,"count":80,"total_weight_g":16000,"component_counts":[5,16]},
                    "url":"https://hb.afl.rakuten.co.jp/hgc/test/?" + urlencode({"pc":"https://item.rakuten.co.jp/likaman/950871-16/"})}
        self.hit = {"code":"likaman_950871-16","janCode":"4973360566850","name":name,
                    "condition":"new","inStock":True,"shipping":{"code":2,"name":"送料無料"},
                    "price":16100,"priceLabel":{"taxable":True},
                    "url":"https://ck.jp.ap.valuecommerce.com/servlet/referral?" + urlencode({"sid":"123","pid":"456","vc_url":self.target})}

    def pair(self, hit=None, **kw):
        return collect_pair([self.row], self.stamp, "test-client", self.config, approved=True,
                            request=lambda *a,**k:[self.hit if hit is None else hit], now=self.now, **kw)

    def test_default_never_calls_api(self):
        def unexpected(*a, **k):
            self.fail("must not contact API")
        self.assertIsNone(collect_pair([self.row], self.stamp, "test-client", self.config, request=unexpected))
        self.assertEqual(render_pair(None), "")

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
