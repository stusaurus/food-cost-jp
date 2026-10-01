import sys
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_site as build
from test_presentation import sample_item, NOW


class MarcheRegressionTests(unittest.TestCase):
    def setUp(self):
        self.results = {c['id']: ([sample_item(c['id'], i) for i in range(1, 5)], [])
                        for c in build.CATEGORIES}

    def test_home_utilities_are_rendered_not_literal(self):
        page = build.home_page(self.results, NOW)
        self.assertIn('data-compare-bar hidden', page)
        self.assertIn('data-saved-modal hidden', page)
        self.assertIn(f'href="{build.SITE_URL}saved/"', page)
        self.assertNotIn('{utility_panels_html()}', page)
        self.assertNotIn('{SITE_URL}', page)

    def test_real_illustration_assets_and_reduced_motion(self):
        for c in build.CATEGORIES:
            self.assertTrue((Path(__file__).parents[1] / 'assets' / f"marche-{c['id']}.webp").exists())
            self.assertNotIn('<svg', build.category_illustration(c['id']))
        self.assertIn('prefers-reduced-motion', build.CSS)
        self.assertIn('[hidden]{display:none!important}', build.CSS)

    def test_new_home_order_and_finder_all_twenty_outcomes(self):
        page = build.home_page(self.results, NOW)
        self.assertLess(page.index('class="section deal-section"'), page.index('id="categories"'))
        self.assertLess(page.index('id="categories"'), page.index('id="quick-finder"'))
        for c in build.CATEGORIES:
            for purpose in ['cheap', 'small', 'large', 'budget', 'storage']:
                self.assertIn(f'data-finder-picks="{c["id"]}:{purpose}" hidden', page)

    def test_rakuten_tracking_and_storage_contract(self):
        page = build.category_page(build.CATEGORIES[0], *self.results['pack-rice'], NOW)
        for hook in ['data-affiliate="rakuten"', 'data-cta-variant', 'data-unit-price',
                     'data-shipping', 'nofollow sponsored noopener',
                     'food_cost_saved_v1', 'food_cost_compare_v1', 'product_compare_add',
                     'price_history_range_change', 'quick_finder_complete']:
            self.assertIn(hook, page)


if __name__ == '__main__':
    unittest.main()
