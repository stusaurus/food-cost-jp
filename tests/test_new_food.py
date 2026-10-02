import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from new_food import parse,rejection,categories

class NewQuantityTests(unittest.TestCase):
    def test_explicit_pack_chains(self):
        cases=[('mineral-water','天然水 500ml×24本',24,12000),('mineral-water','天然水 500ml×24本×2箱',48,24000),('mineral-water','天然水 2L×6本',6,12000),('pasta','スパゲッティ 500g×6袋',6,3000),('pasta','スパゲッティ 1kg×5袋',5,5000),('pasta','スパゲッティ 500g×6袋×2箱',12,6000),('granola','グラノーラ 750g×6袋',6,4500),('retort-curry','レトルトカレー 180g×10食',10,1800),('retort-curry','レトルトカレー 200g×10袋×2箱',20,4000),('bag-noodles','袋麺 5食×6袋',30,None),('bag-noodles','袋麺 5食×6袋×2箱',60,None),('cup-noodles','カップ麺 12個入り',12,None),('cup-noodles','カップ麺 78g×12個',12,None)]
        for cid,title,count,total in cases:
            with self.subTest(title=title):
                q=parse(title,cid);self.assertIsNotNone(q);self.assertEqual(q['count'],count)
                if total:self.assertEqual(q.get('total_weight_g',q.get('total_volume_ml')),total)
    def test_ambiguous_or_unaccounted_quantities_fail(self):
        cases=[('mineral-water','天然水 500ml×24本 2箱'),('mineral-water','天然水 500ml×24本×2箱 計24本'),('mineral-water','天然水 500ml×24本×2箱 2本'),('bag-noodles','袋麺 5食×6袋 6食'),('pasta','スパゲッティ 500g×6袋×2箱 合計6袋'),('mineral-water','天然水 500ml×24本×2'),('mineral-water','天然水 500ml 1L 24本'),('pasta','スパゲッティ 500g 1kg'),('pasta','スパゲッティ 500g×6袋 12袋'),('granola','グラノーラ 選べる 500g×6袋'),('retort-curry','レトルトカレー 180g×10袋 200g×10袋'),('retort-curry','レトルトカレー 1000g×10袋'),('bag-noodles','袋麺 5食×6袋 20食'),('bag-noodles','袋麺 6袋'),('bag-noodles','マルちゃん正麺 5P×2個セット'),('cup-noodles','カップ麺 個数不明'),('cup-noodles','カップ麺 40g×12個'),('cup-noodles','カップ麺 12個×2')]
        for cid,title in cases:
            with self.subTest(title=title):self.assertIsNone(parse(title,cid))
    def test_wrong_types_and_restricted_purchases_fail(self):
        examples={'mineral-water':['炭酸 天然水','天然水 フレーバー','天然水 ウォーターサーバー','天然水 お茶'],'pasta':['スパゲッティ ソース','生パスタ スパゲッティ','冷凍スパゲッティ','スパゲッティ ギフト'],'granola':['グラノーラバー','グラノーラ プロテイン','グラノーラ オートミール','ノースイ ミックスベリーフローズン500g グラノーラのトッピングに'],'retort-curry':['レトルト カレールー','レトルトカレー ご飯付き','レトルトカレー 冷凍'],'bag-noodles':['袋麺 カップ','袋麺 生麺','袋麺 麺のみ','一蘭 ラーメン 博多細麺 5食 袋麺','一風堂監修 袋麺 5食'],'cup-noodles':['カップ麺 ミニ','カップ麺 ビッグ','カップ麺 大盛','麻辣湯 カップ麺 12個 即席春雨 さつま芋麺']}
        for cid,titles in examples.items():
            for title in titles:
                with self.subTest(title=title):self.assertIsNotNone(rejection(cid,title))
        for c in categories():
            for word in ['定期便','初回限定','会員限定','選べる','福袋']:
                self.assertIsNotNone(rejection(c['id'],c['name']+' '+word))

class NewCategoryIntegrationTests(unittest.TestCase):
    def test_normalization_and_units_for_each_new_category(self):
        import build_site as b
        cases=[('mineral-water','天然水 500ml×24本×2箱','per_liter',100),('pasta','スパゲッティ 500g×6袋','per_100g',80),('granola','グラノーラ 500g×6袋','per_100g',80),('retort-curry','レトルトカレー 180g×10食','per_serving',240),('bag-noodles','サッポロ一番 5食×6袋','per_serving',80),('cup-noodles','カップ麺 78g×12個','per_serving',200)]
        for cid,title,metric,unit in cases:
            c=next(c for c in b.CATEGORIES if c['id']==cid)
            raw=dict(itemName=title,itemPrice=2400,itemCode='shop:'+cid,itemUrl='https://example.com/'+cid,postageFlag=0)
            with self.subTest(category=cid):
                item=b.normalize_item(raw,c);self.assertIsNotNone(item);self.assertAlmostEqual(item['unit_prices'][metric],unit)
                self.assertTrue(item['postage_included'])
                raw['postageFlag']=1;item=b.normalize_item(raw,c);self.assertFalse(item['postage_included'])
                raw['itemName']='【1000円OFFクーポン】'+title;item=b.normalize_item(raw,c);self.assertEqual(item['price'],2400)
    def test_sparse_new_category_is_hidden_and_noindex(self):
        import build_site as b
        from test_presentation import sample_item,NOW
        c=next(c for c in b.CATEGORIES if c['id']=='pasta')
        items=[sample_item('pasta',1),sample_item('pasta',2)]
        self.assertNotIn(c,b.active_categories({'pasta':(items,[])}))
        page=b.category_page(c,items,[],NOW);self.assertIn('content="noindex,follow"',page)
    def test_new_category_seo_and_four_department_navigation(self):
        import build_site as b
        from test_presentation import sample_item,NOW
        results={c['id']:([sample_item(c['id'],i) for i in range(1,5)],[]) for c in b.CATEGORIES}
        page=b.home_page(results,NOW)
        self.assertEqual(page.count('class="aisle-card"'),4)
        self.assertEqual(page.count('class="finder-aisle"'),4)
        for c in b.CATEGORIES:
            cat=b.category_page(c,*results[c['id']],NOW)
            for schema in ['BreadcrumbList','ItemList','FAQPage']:
                self.assertIn(schema,cat)
            self.assertIn('categories/'+c['id']+'/',cat)
            self.assertIn('data-finder-category="'+c['id']+'"',page)
    def test_water_signature_and_history_reset_are_size_sensitive(self):
        import build_site as b
        from product_quality import quantity_signature
        a=parse('天然水 500ml×24本','mineral-water');d=parse('天然水 1L×12本','mineral-water')
        self.assertNotEqual(quantity_signature('mineral-water',a),quantity_signature('mineral-water',d))
    def test_optimization_audit_exposes_fetch_and_exclusions(self):
        import build_site as b
        from test_presentation import NOW
        audits={'pasta':dict(fetched=90,normalized=30,reasons={'ambiguous_quantity':4})}
        report=b.optimization_report({},[],NOW,audits)
        self.assertEqual(report['inventory']['pasta']['quality_audit']['fetched'],90)
        self.assertEqual(report['inventory']['pasta']['publication_status'],'deferred_insufficient_safe_inventory')
