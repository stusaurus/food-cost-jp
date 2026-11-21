"""Ensure the water-cost decision page is generated, linked and honest."""
import tempfile
import unittest
from pathlib import Path

from scripts import water_server_compare as w


class WaterServerCompareTests(unittest.TestCase):
    def test_page_has_canonical_and_official_a8_creative(self):
        page = w.page()
        self.assertIn('<link rel="canonical" href="' + w.URL + '">', page)
        self.assertIn('ペットボトル', page)
        self.assertIn('ウォーターサーバー', page)
        self.assertIn('1年間に実際に払う費用', page)
        self.assertIn("Math.ceil(L * 12 / (b * c))", page)
        self.assertIn("inputs[\"server-per-liter\"]", page)
        self.assertIn('results.classList.add("visible")', page)
        self.assertIn('広告｜A8.netアフィリエイト', page)
        self.assertIn('サーバーの契約条件を確認する', page)
        self.assertIn(w.A8_EVERY_FRECIOUS_AD, page)
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)
        self.assertEqual(page.count('https://px.a8.net/svt/ejp?'), 2)  # in creative and tracking selector
        self.assertIn('<img border="0" width="1" height="1" src="https://www17.a8.net/0.gif?', page)
        self.assertIn('"affiliate_click"', page)
        self.assertIn('"water_server_cost_comparison"', page)
        self.assertIn("window.foodCostOperatorTest", page)
        self.assertNotIn('shizukuria', page.lower())
        self.assertNotIn('nosh', page.lower())

    def test_changed_inputs_invalidate_old_annual_result_and_respect_yen_step(self):
        page = w.page()
        self.assertIn('fields.forEach(id => {', page)
        self.assertIn('results.classList.remove("visible");', page)
        self.assertIn('$(id).addEventListener("input", () => { invalidate(); clearSource(); });', page)
        self.assertIn('$(id).addEventListener("change", () => { invalidate(); clearSource(); });', page)
        self.assertIn('fields.some(id => !$(id).checkValidity())', page)
        self.assertIn("金額・ケース本数は整数で入力してください", page)
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)

    def test_example_rates_and_monthly_metrics_do_not_claim_live_vendor_prices(self):
        page = w.page()
        self.assertIn('id="example" type="button"', page)
        self.assertIn('id="example-warning" class="notice" hidden', page)
        self.assertIn('現在の販売価格・各社の契約料金ではありません', page)
        self.assertIn('id="bottle-monthly"', page)
        self.assertIn('id="server-monthly"', page)
        self.assertIn('id="bottle-effective"', page)
        self.assertIn('id="server-effective"', page)
        self.assertIn('"case-price": 900', page)
        self.assertIn('money(bottledYear / 12)', page)
        self.assertIn('amount / used', page)
        self.assertIn('月ごとの支払額は均等ではありません', page)
        # Keep the independent source-owned A8 creative, not guessed plan rates.
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)

    def test_verified_water_offer_selector_uses_only_safe_exact_prices_and_sizes(self):
        from datetime import datetime
        base = {
            "name": "送料込2L水 <特価>",
            "id": "shop:2l",
            "price": 1836,
            "url": "https://hb.afl.rakuten.co.jp/hgc/valid/?pc=safe",
            "postage_included": True, "shipping_status": "included",
            "quantity": {"count": 12, "unit_volume_ml": 2000,
                         "total_volume_ml": 24000, "confidence": 0.99},
        }
        other_size = {**base, "name": "500ml×48本",
                      "id": "shop:500ml", "price": 2610,
                      "quantity": {"count": 48, "unit_volume_ml": 500,
                                   "total_volume_ml": 24000, "confidence": 0.99}}
        expensive_same_size = {**base, "name": "同容量で高い",
                               "price": 1888}
        not_included = {**base, "name": "送料不明", "price": 100,
                        "postage_included": False, "shipping_status": "unknown"}
        wrong_total = {**base, "name": "本数不一致", "price": 100,
                       "quantity": {"count": 24, "unit_volume_ml": 2000,
                                    "total_volume_ml": 24000, "confidence": 0.99}}
        low_confidence = {**base, "name": "数量不確定", "price": 100,
                          "quantity": {"count": 12, "unit_volume_ml": 2000,
                                       "total_volume_ml": 24000, "confidence": 0.2}}
        invalid_link = {**base, "name": "非楽天リンク", "price": 100,
                        "url": "https://example.com/wrong"}
        page = w.page(water_offers=[
            not_included, wrong_total, low_confidence, invalid_link,
            expensive_same_size, other_size, base
        ], checked_at=datetime(2026, 11, 21, 8, 39))
        self.assertEqual(page.count("data-water-offer data-bottle-liters="), 2)
        self.assertIn("2026-11-21 08:39 JST", page)
        self.assertIn('data-bottle-liters="2" data-case-count="12" data-case-price="1836"', page)
        self.assertIn('data-bottle-liters="0.5" data-case-count="48" data-case-price="2610"', page)
        self.assertIn("¥1,836／購入セット", page)
        self.assertIn("¥76.5／L", page)
        self.assertIn("送料込2L水 &lt;特価&gt;", page)
        for removed in ("送料不明", "本数不一致", "数量不確定", "非楽天リンク", "同容量で高い"):
            self.assertNotIn(removed, page)
        self.assertEqual(page.count('data-water-rakuten-offer data-product-id='), 2)
        self.assertIn('rel="nofollow sponsored noopener"', page)
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)
        self.assertIn('window.gtag("event", "water_offer_prefill"', page)
        self.assertIn('click_position: "water_cost_verified_offer"', page)

    def test_no_valid_water_offers_keep_manual_planner_without_fabricated_prices(self):
        page = w.page(water_offers=[{
            "name": "送料別の格安水", "price": 100,
            "postage_included": False, "shipping_status": "unknown",
            "quantity": {"count": 12, "unit_volume_ml": 2000, "total_volume_ml": 24000},
            "url": "https://hb.afl.rakuten.co.jp/hgc/valid/"
        }])
        self.assertNotIn('data-water-offer data-bottle-liters=', page)
        self.assertNotIn("送料別の格安水", page)
        self.assertIn('id="calculate"', page)
        self.assertIn('id="example"', page)
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)

    def test_reuses_the_existing_ga4_head_in_generated_page(self):
        ga = '<script>window.gtag=function(){return true};window.foodCostOperatorTest=true;</script>'
        page = w.page(ga)
        self.assertEqual(page.count(ga), 1)
        self.assertLess(page.index(ga), page.index('</head>'))
        self.assertEqual(page.count(w.A8_EVERY_FRECIOUS_AD), 1)

    def test_publishes_page_and_links_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"categories/mineral-water").mkdir(parents=True)
            (root/"index.html").write_text('<html><body><main><h1>食品</h1></main></body></html>')
            (root/"categories/mineral-water/index.html").write_text(
                '<html><body><main><h1>水</h1></main></body></html>')
            (root/"sitemap.xml").write_text(
                '<?xml version="1.0"?><urlset><url><loc>https://example.invalid/</loc></url></urlset>')
            self.assertEqual(w.publish(root), root/"guides"/w.SLUG/"index.html")
            self.assertEqual(w.publish(root), root/"guides"/w.SLUG/"index.html")
            for target in ("index.html", "categories/mineral-water/index.html"):
                text = (root/target).read_text()
                self.assertEqual(text.count(w.MARKER), 1)
                self.assertIn("/food-cost-jp/guides/"+w.SLUG+"/",text)
            self.assertEqual((root/"sitemap.xml").read_text().count(w.URL),1)
            published = (root/"guides"/w.SLUG/"index.html").read_text()
            self.assertIn(w.A8_EVERY_FRECIOUS_AD, published)
            self.assertEqual(published.count('a8mat=4BGCF1+53DLEY+2B8Y+15OK2A'), 2)

    def test_fails_closed_for_unexpected_missing_page(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"index.html").write_text('<html></html>')
            (root/"sitemap.xml").write_text('<urlset></urlset>')
            with self.assertRaises(ValueError):
                w.publish(root)


if __name__ == "__main__":
    unittest.main()
