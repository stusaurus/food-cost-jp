import unittest
from copy import deepcopy
from test_marche import build, sample_item, NOW

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.results={c['id']:([sample_item(c['id'],i) for i in range(1,5)],[]) for c in build.CATEGORIES}
    def test_empty_small_never_falls_back_to_large(self):
        c=build.CATEGORIES[0]
        self.assertEqual(build.finder_pick_items([sample_item(c['id'],2)],c,'small'),[])
        self.assertIn('掲載候補は現在ありません',build.market_shelf_html([], '少量','empty','small'))
    def test_unknown_shipping_not_recommended(self):
        c=build.CATEGORIES[0];item=sample_item(c['id']);item['postage_included']=False
        self.assertEqual(build.finder_pick_items([item],c,'budget'),[])
    def test_storage_uses_total_bottle_volume(self):
        item=sample_item('carbonated-water');item['quantity']['count']=48;item['quantity']['total_volume_ml']=24000
        self.assertEqual(build.shopping_bucket(item,'carbonated-water'),'large')
        self.assertEqual(build.bucket(item,'carbonated-water'),'small') # existing bottle filter preserved
    def test_cross_shelf_has_one_per_aisle_without_global_unit_ranking(self):
        entries=build.cross_shelf_items(self.results,'budget')
        self.assertEqual([c['id'] for c,_ in entries],[c['id'] for c in build.CATEGORIES])
        self.assertTrue(all(item['price']==2401 for _,item in entries))
    def test_price_drop_evidence_and_reason(self):
        item=self.results['rice'][0][2];item['price_history']={'price_delta':-100,'observed_days':2,'is_30d_low':True}
        entries=build.cross_shelf_items(self.results,'cheap')
        self.assertEqual(dict((c['id'],i['id']) for c,i in entries)['rice'],item['id'])
        shelf=build.market_shelf_html(entries,'本日','today')
        self.assertIn('前回取得時より価格が下がった掲載商品',shelf)
        self.assertNotIn('前回取得時より価格が下がった掲載商品',build.market_shelf_html([(build.CATEGORIES[1],item)],'単価','finder-rice-cheap'))
    def test_home_information_order_and_hidden_category_step(self):
        page=build.home_page(self.results,NOW)
        positions=[page.index(x) for x in ['class="home-hero"','id="today-market"','id="quick-finder"','class="section discovery-shelves"','id="categories"']]
        self.assertEqual(positions,sorted(positions))
        self.assertIn('data-finder-category-stage hidden',page)
        self.assertIn('data-finder-purpose="known"',page)
        self.assertIn('価格履歴を蓄積中',page)
    def test_price_order_versus_unit_order(self):
        c=build.CATEGORIES[0];items=self.results[c['id']][0]
        items[0]['price']=9000
        self.assertEqual(build.finder_pick_items(items,c,'cheap')[0]['id'],items[0]['id'])
        self.assertNotEqual(build.finder_pick_items(items,c,'budget')[0]['id'],items[0]['id'])
