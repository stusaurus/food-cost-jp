"""Ensure the water-cost decision page is generated, linked and honest."""
import tempfile
import unittest
from pathlib import Path

from scripts import water_server_compare as w


class WaterServerCompareTests(unittest.TestCase):
    def test_page_has_canonical_and_no_fake_server_offer(self):
        page = w.page()
        self.assertIn('<link rel="canonical" href="' + w.URL + '">', page)
        self.assertIn('ペットボトル', page)
        self.assertIn('ウォーターサーバー', page)
        self.assertIn('1年間に実際に払う費用', page)
        self.assertIn("Math.ceil(L * 12 / (b * c))", page)
        self.assertIn("inputs[\"server-per-liter\"]", page)
        self.assertIn('results.classList.add("visible")', page)
        self.assertIn('提携確認前のため掲載していません', page)
        self.assertNotIn('a8.net/', page)
        self.assertNotIn('shizukuria', page.lower())
        self.assertNotIn('nosh', page.lower())

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
            self.assertTrue((root/"guides"/w.SLUG/"index.html").exists())

    def test_fails_closed_for_unexpected_missing_page(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"index.html").write_text('<html></html>')
            (root/"sitemap.xml").write_text('<urlset></urlset>')
            with self.assertRaises(ValueError):
                w.publish(root)


if __name__ == "__main__":
    unittest.main()
