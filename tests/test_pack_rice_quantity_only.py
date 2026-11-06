"""No trustworthy offer means count-only fallback, not invented shopping advice."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pack_rice_planner import render_planner, render_quantity_only_planner
from build_site import AUTO_GUIDE_RULES, CATEGORIES, guide_page

NOW = datetime(2026, 11, 6, 20, 0, tzinfo=ZoneInfo('Asia/Tokyo'))


class QuantityOnlyGuideTests(unittest.TestCase):
    def setUp(self):
        self.spec = next(x for x in AUTO_GUIDE_RULES
                         if x['slug'] == 'pack-rice-24-servings-cost')
        self.category = next(x for x in CATEGORIES if x['id'] == 'pack-rice')

    def test_empty_or_unverified_offer_yields_quantity_only_not_fake_price(self):
        html = guide_page(self.spec, self.category, [], NOW)
        self.assertEqual(render_planner([], NOW), '')
        self.assertIn('data-rice-quantity-only', html)
        self.assertIn('pack-rice-quantity-only.js', html)
        self.assertNotIn('data-rice-planner-buy', html)
        self.assertNotIn('data-rice-planner-product', html)
        self.assertIn('支払総額は計算できません', html)
        self.assertIn('商品価格・販売先・送料・購入リンクは表示できません', html)
        self.assertIn('<meta name="robots" content="noindex,follow">', html)
        self.assertEqual(html.count('rel="canonical"'), 1)
        self.assertEqual(html.count('<h1'), 1)

    def test_quantity_fallback_contains_usable_numerical_controls_and_no_link(self):
        html = render_quantity_only_planner()
        self.assertIn('data-rice-quantity-daily', html)
        self.assertIn('data-rice-quantity-days', html)
        self.assertIn('data-rice-quantity-stock', html)
        for n in (1, 2, 3, 4):
            self.assertIn(f'data-rice-quantity-choice="{n}"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('30食不足', html)
        self.assertIn('2箱', html)
        self.assertNotIn('href="https://item.rakuten.co.jp', html)
        self.assertNotIn('data-affiliate=', html)

    def test_non_pack_rice_guides_do_not_inherit_quantity_fallback(self):
        category = next(x for x in CATEGORIES if x['id'] == 'rice')
        spec = next(x for x in AUTO_GUIDE_RULES if x['category_id'] == 'rice')
        html = guide_page(spec, category, [], NOW)
        self.assertNotIn('data-rice-quantity-only', html)
        self.assertNotIn('pack-rice-quantity-only.js', html)


if __name__ == '__main__':
    unittest.main()
