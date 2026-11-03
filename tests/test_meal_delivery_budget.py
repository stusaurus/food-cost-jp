"""A8 chef Muten cost-planner link and honest-fee regression tests."""
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from scripts import meal_delivery_budget as budget


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.pixels, self.h1, self.canonicals, self.ad_labels = [], [], 0, [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and 'px.a8.net' in a.get('href', ''):
            self.links.append(a)
        if tag == 'img' and 'a8.net/0.gif' in a.get('src', ''):
            self.pixels.append(a)
        if tag == 'h1':
            self.h1 += 1
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonicals.append(a.get('href'))


class MealDeliveryBudgetTests(unittest.TestCase):
    def test_advertiser_a8_code_and_pixel_exactly_preserved(self):
        page = budget.page()
        budget.validate_creative(page)
        self.assertEqual(page.count(budget.A8_CHEF_MUTEN), 1)
        tags = Tags(page)
        self.assertEqual(tags.links, [{
            'href': 'https://px.a8.net/svt/ejp?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM',
            'rel': 'nofollow',
        }])
        self.assertEqual(tags.pixels, [{
            'border': '0', 'width': '1', 'height': '1',
            'src': 'https://www19.a8.net/0.gif?a8mat=4BGCF1+8J7R8Q+57YO+5YJRM',
            'alt': '',
        }])
        self.assertEqual(tags.h1, 1)
        self.assertEqual(tags.canonicals, [budget.URL])
        self.assertEqual(page.count('広告｜A8.netアフィリエイト'), 1)
        self.assertIn('栄養上の適合や食品の安全性を当サイトが保証するものではありません', page)
        self.assertIn('広告主提供の表現', page)

    def test_calculator_differentiates_first_and_regular_orders_and_shipping(self):
        page = budget.page()
        for term in (
            'meal-first-price', 'meal-first-shipping',
            'meal-regular-price', 'meal-regular-shipping',
            'meal-deliveries', 'meal-include-first', 'meal-calculate',
            '初回注文を含める', 'スキップ', '2回目以降', '消費期限',
        ):
            self.assertIn(term, page)
        self.assertIn("firstCount * values['meal-first-price']", page)
        self.assertIn("regularCount * values['meal-regular-price']", page)
        self.assertIn("shipping = firstCount * values['meal-first-shipping']", page)
        self.assertIn("operator_test:window.foodCostOperatorTest?'1':'0'", page)
        self.assertIn("conversion_source:'family_meal_budget_planner'", page)
        self.assertNotIn('いつでもキャンセル可能', page)
        self.assertIn('公式FAQ', page)
        self.assertIn("first:3799", page)
        self.assertIn("regular:13607", page)

    def test_ga4_head_reused_and_no_duplicate_ad(self):
        head = "<script>window.gtag=function(){};window.foodCostOperatorTest=true;</script>"
        page = budget.page(head)
        self.assertEqual(page.count(head), 1)
        self.assertLess(page.index(head), page.index('</head>'))
        self.assertEqual(page.count(budget.A8_CHEF_MUTEN), 1)

    def test_publish_is_idempotent_and_links_home_and_sitemap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'index.html').write_text('<html><body><main><h1>食品コスパ比較</h1></main></body></html>')
            (root / 'sitemap.xml').write_text(
                '<?xml version="1.0"?><urlset><url><loc>https://example.invalid/</loc></url></urlset>')
            self.assertEqual(budget.publish(root), root / 'guides' / budget.SLUG / 'index.html')
            self.assertEqual(budget.publish(root), root / 'guides' / budget.SLUG / 'index.html')
            home = (root / 'index.html').read_text()
            self.assertEqual(home.count(budget.MARKER), 1)
            self.assertEqual(home.count(budget.URL), 1)
            self.assertEqual((root / 'sitemap.xml').read_text().count(budget.URL), 1)
            self.assertEqual((root / 'guides' / budget.SLUG / 'index.html').read_text().count(budget.A8_CHEF_MUTEN), 1)

    def test_fails_closed_if_home_missing_or_creative_changed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'sitemap.xml').write_text('<urlset></urlset>')
            with self.assertRaises(ValueError):
                budget.publish(root)
            (root / 'index.html').write_text('<html><body>no main</body></html>')
            with self.assertRaises(ValueError):
                budget.publish(root)
        page = budget.page()
        with self.assertRaises(ValueError):
            budget.validate_creative(page.replace("www19.a8.net", "www18.a8.net"))
        with self.assertRaises(ValueError):
            budget.validate_creative(page + budget.A8_CHEF_MUTEN)
        with self.assertRaises(ValueError):
            budget.validate_creative(page.replace('広告｜A8.netアフィリエイト', ''))


if __name__ == "__main__":
    unittest.main()
