import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_site as b
from validate_generated_site import validate_products, validate_pages, validate_sitemap
from product_quality import quantity_conflict

class FinalAuditTests(unittest.TestCase):
    def test_nested_package_regression_counts_36_servings(self):
        title='ベイシア 国産米 （180g×6パック入）×6個 ケース販売 パックご飯'
        q=b.parse_quantity(title,'pack-rice')
        self.assertEqual(q['count'],36)
        self.assertEqual(q['total_weight_g'],6480)
        self.assertFalse(quantity_conflict(title,'pack-rice',q))
        self.assertAlmostEqual(b.unit_prices(3600,q,'pack-rice')['per_serving'],100)

    def test_conflicting_capacity_and_promo_capacity_are_rejected(self):
        cases=[('carbonated-water','炭酸水 500ml×24本 1L×24本'),('pack-rice','パックご飯 180g×24食 200g'),('oatmeal','オートミール 1kg×2袋 3kg'),('rice','新米実質5kg2390円 選べる各種銘柄米')]
        for cid,title in cases:
            c=next(c for c in b.CATEGORIES if c['id']==cid)
            with self.subTest(title=title):
                x=b.normalize_item(dict(itemName=title,itemPrice=3000,itemUrl='https://example.com',postageFlag=0),c)
                self.assertIsNone(x)

    def test_repeated_quantity_does_not_lose_valid_product(self):
        title='パックご飯 180g×24食 アイリス 180g×24食'
        q=b.parse_quantity(title,'pack-rice');self.assertFalse(quantity_conflict(title,'pack-rice',q))
        title='オートミール 1200g(1.2kg)×1個'
        q=b.parse_quantity(title,'oatmeal');self.assertFalse(quantity_conflict(title,'oatmeal',q))

    def test_all_guides_apply_floor_and_equal_lists_consolidate(self):
        data=json.loads(Path('data/products.json').read_text())
        results={cid:(v['included'],v['shipping_unknown']) for cid,v in data['categories'].items()}
        published,aliases=b.publication_guides(results)
        signatures=set()
        for s in published:
            c=next(c for c in b.CATEGORIES if c['id']==s['category_id'])
            items=b.guide_filter_items(s,results[c['id']][0],c)
            self.assertGreaterEqual(len(items),3)
            signature=(c['id'],tuple(sorted(x['id'] for x in items)))
            self.assertNotIn(signature,signatures);signatures.add(signature)
        results['rice']=(results['rice'][0][:1],[])
        self.assertFalse(any(s['category_id']=='rice' for s in b.publication_guides(results)[0]))

    def test_daily_discovery_rotates_only_close_top_offers(self):
        from test_presentation import sample_item
        items=[sample_item('rice',i) for i in range(1,5)]
        for x,unit in zip(items,[100,102,105,150]): x['unit_prices']['per_kg']=unit;x['price_history']={}
        results={'rice':(items,[])}
        picks={b.cross_shelf_items(results,'cheap',day=f'2026-10-{day:02}')[0][1]['id'] for day in range(1,20)}
        self.assertGreater(len(picks),1);self.assertNotIn(items[3]['id'],picks)
        items[3]['price_history']={'price_delta':-100,'percent_delta':-10}
        self.assertEqual(b.cross_shelf_items(results,'cheap',day='2026-10-02')[0][1]['id'],items[3]['id'])

    def test_gate_catches_price_duplicate_shipping_and_fetch_failure(self):
        data=json.loads(Path('data/products.json').read_text())
        for mutate in ('price','duplicate','shipping','fetch','collapse'):
            bad=copy.deepcopy(data);p=bad['categories']['pasta'];x=p['included'][0]
            if mutate=='price':x['unit_prices']['per_100g']*=2
            if mutate=='duplicate':p['included'].append(copy.deepcopy(x))
            if mutate=='shipping':x['postage_included']=False
            if mutate=='fetch':p['quality_audit']['fetch_errors']=1
            if mutate=='collapse':p['included']=p['included'][:2]
            with self.subTest(mutate=mutate):
                errors=validate_products(bad,data)
                expected={'price':'incorrect unit','duplicate':'duplicate product','shipping':'shipping classification','fetch':'API query failed','collapse':'inventory collapsed'}[mutate]
                self.assertTrue(any(expected in e for e in errors),errors)

    def test_page_gate_rejects_malformed_json_missing_link_and_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            content=b.page_head('Audit','Audit',b.SITE_URL,'<script type="application/ld+json">broken</script>')+'<h1>Audit</h1><a href="missing/">Missing</a>'
            (root/'index.html').write_text(content)
            (root/'orphan').mkdir();(root/'orphan/index.html').write_text(b.page_head('Orphan','Orphan',b.SITE_URL+'orphan/')+'<h1>Orphan</h1>')
            errors,_=validate_pages(root,set())
            for kind in ('malformed structured','broken internal','orphan indexable'):
                self.assertTrue(any(kind in e for e in errors),errors)
            (root/'sitemap.xml').write_text('<broken')
            self.assertTrue(validate_sitemap(root,[root/'index.html']))

    def test_query_overlap_deduplicates_same_listing_with_changed_price(self):
        c=next(c for c in b.CATEGORIES if c['id']=='rice')
        raw=dict(itemName='国産米 5kg',itemPrice=3000,itemUrl='https://example.com/item',itemCode='shop:item',postageFlag=0)
        with patch.object(b,'fetch',return_value=[raw,{**raw,'itemPrice':3100}]),patch.object(b.time,'sleep'):
            included,_,audit=b.collect(c)
        self.assertEqual(len(included),1);self.assertGreater(audit['exact_duplicates'],0)

if __name__=='__main__': unittest.main()
