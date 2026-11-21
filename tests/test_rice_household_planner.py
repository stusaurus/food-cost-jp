"""Regression tests for the 5kg/10kg household rice purchase planner."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from scripts import rice_household_planner as r


def offer(grams, price, product_id=None, name=None):
    return {
        "id": product_id or "shop:item" + str(grams),
        "name": name or "国産精米 " + str(grams // 1000) + "kg",
        "price": price,
        "postage_included": True,
        "shipping_status": "included",
        "url": "https://hb.afl.rakuten.co.jp/hgc/verified/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fshop%2Fitem%2F",
        "quantity": {
            "total_weight_g": grams,
            "unit_weight_g": grams,
            "count": 1,
            "confidence": 0.99,
        },
    }


class HouseholdRicePlannerTests(unittest.TestCase):
    def test_eligible_exact_5kg_and_10kg_only(self):
        five = offer(5000, 2720)
        ten = offer(10000, 3480)
        bad = [
            {**five, "price": 100, "shipping_status": "extra_or_unknown", "postage_included": False},
            {**five, "price": 100, "quantity": {**five["quantity"], "confidence": 0.5}},
            {**ten, "price": 100, "quantity": {**ten["quantity"], "total_weight_g": 9000}},
            {**ten, "price": 100, "url": "https://example.net/out"},
            {**ten, "price": 100, "url": "https://hb.afl.rakuten.co.jp/hgc/verified/?pc=https%3A%2F%2Fevil.invalid%2F"},
            {**ten, "price": 100, "name": "北海道配送不可"},
            {**ten, "price": 100, "quantity": {**ten["quantity"], "total_weight_g": 15000}},
            {**ten, "price": 100.5},
            {**ten, "price": True},
        ]
        chosen = r.eligible_offers(bad + [five, ten])
        self.assertEqual(set(chosen), {5000, 10000})
        self.assertEqual(chosen[5000]["price"], 2720)
        self.assertEqual(chosen[10000]["price"], 3480)
        self.assertFalse(r.eligible_offers([five]))
        self.assertFalse(r.eligible_offers([ten]))
        self.assertFalse(r.eligible_offers(bad))

    def test_precise_source_page_and_paid_link_attributes(self):
        five, ten = offer(5000, 2720), offer(10000, 3480)
        five["name"] = '訳あり <script>alert("x")</script> 5kg'
        page = r.page([five, ten], datetime(2026, 11, 21, 10, 10))
        self.assertIsNotNone(page)
        self.assertIn('<link rel="canonical" href="' + r.URL + '">', page)
        self.assertIn('米5kg・10kgは何日もつ', page)
        self.assertIn('2026-11-21 10:10 JST', page)
        self.assertIn('訳あり &lt;script&gt;', page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn('1合＝約150g', page)
        self.assertIn(r.MAFF, page)
        self.assertIn('5kgは約16.7日分', page)
        self.assertIn('10kgは約33.3日分', page)
        self.assertIn('data-kg="5" data-price="2720"', page)
        self.assertIn('data-kg="10" data-price="3480"', page)
        self.assertEqual(page.count('data-affiliate="rakuten"'), 2)
        self.assertEqual(page.count('data-position="rice_household_planner"'), 2)
        self.assertEqual(page.count('rel="nofollow sponsored noopener"'), 2)
        self.assertEqual(page.count('data-metric="per_kg"'), 2)
        self.assertEqual(page.count('data-shipping="included"'), 2)
        self.assertIn('data-unit-price="544.000000"', page)
        self.assertIn('data-unit-price="348.000000"', page)
        self.assertNotIn("px.a8.net", page)
        self.assertIn("クーポンやポイント還元は差し引きません", page)

    def test_publisher_adds_one_internal_link_each_and_one_canonical_sitemap_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ("index.html", "categories/rice/index.html",
                     "guides/rice-5kg-cost/index.html", "guides/rice-10kg-cost/index.html")
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("<html><main><h1>米</h1></main></html>", encoding="utf-8")
            (root / "sitemap.xml").write_text(
                '<?xml version="1.0"?><urlset><url><loc>https://example.invalid/</loc></url></urlset>',
                encoding="utf-8"
            )
            kwargs = dict(rice_offers=[offer(5000, 2720), offer(10000, 3480)],
                          checked_at=datetime(2026, 11, 21, 10, 10))
            self.assertTrue(r.publish(root, **kwargs))
            self.assertTrue(r.publish(root, **kwargs))
            self.assertEqual((root / "sitemap.xml").read_text().count(r.URL), 1)
            for path in paths:
                text = (root / path).read_text()
                self.assertEqual(text.count(r.MARKER), 1)
                self.assertIn('/food-cost-jp/guides/' + r.SLUG + '/', text)
            self.assertTrue((root / "guides" / r.SLUG / "index.html").exists())

    def test_no_unverified_both_sizes_fails_closed_without_indexable_guide(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<html><main></main></html>", encoding="utf-8")
            (root / "sitemap.xml").write_text("<urlset></urlset>", encoding="utf-8")
            self.assertFalse(r.publish(root, rice_offers=[offer(5000, 2720)]))
            self.assertFalse((root / "guides" / r.SLUG / "index.html").exists())
            self.assertNotIn(r.URL, (root / "sitemap.xml").read_text())
            with self.assertRaises(ValueError):
                r.publish(root, rice_offers=[offer(5000, 2720), offer(10000, 3480)])


if __name__ == "__main__":
    unittest.main()
