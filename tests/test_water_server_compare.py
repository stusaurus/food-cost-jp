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
        self.assertIn('$(id).addEventListener("input", invalidate);', page)
        self.assertIn('$(id).addEventListener("change", invalidate);', page)
        self.assertIn('fields.some(id => !$(id).checkValidity())', page)
        self.assertIn("金額・ケース本数は整数で入力してください", page)
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
