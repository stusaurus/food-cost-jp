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
        cases=[('mineral-water','天然水 500ml×24本 2箱'),('mineral-water','天然水 500ml×24本×2'),('mineral-water','天然水 500ml 1L 24本'),('pasta','スパゲッティ 500g 1kg'),('pasta','スパゲッティ 500g×6袋 12袋'),('granola','グラノーラ 選べる 500g×6袋'),('retort-curry','レトルトカレー 180g×10袋 200g×10袋'),('retort-curry','レトルトカレー 1000g×10袋'),('bag-noodles','袋麺 5食×6袋 20食'),('bag-noodles','袋麺 6袋'),('cup-noodles','カップ麺 個数不明'),('cup-noodles','カップ麺 40g×12個'),('cup-noodles','カップ麺 12個×2')]
        for cid,title in cases:
            with self.subTest(title=title):self.assertIsNone(parse(title,cid))
    def test_wrong_types_and_restricted_purchases_fail(self):
        examples={'mineral-water':['炭酸 天然水','天然水 フレーバー','天然水 ウォーターサーバー','天然水 お茶'],'pasta':['スパゲッティ ソース','生パスタ スパゲッティ','冷凍スパゲッティ','スパゲッティ ギフト'],'granola':['グラノーラバー','グラノーラ プロテイン','グラノーラ オートミール'],'retort-curry':['レトルト カレールー','レトルトカレー ご飯付き','レトルトカレー 冷凍'],'bag-noodles':['袋麺 カップ','袋麺 生麺','袋麺 麺のみ'],'cup-noodles':['カップ麺 ミニ','カップ麺 ビッグ','カップ麺 大盛']}
        for cid,titles in examples.items():
            for title in titles:
                with self.subTest(title=title):self.assertIsNotNone(rejection(cid,title))
        for c in categories():
            for word in ['定期便','初回限定','会員限定','選べる','福袋']:
                self.assertIsNotNone(rejection(c['id'],c['name']+' '+word))
