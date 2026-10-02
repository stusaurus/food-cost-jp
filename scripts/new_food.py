"""Conservative first-wave food candidates. No capacity guesses from descriptions."""
import re
from product_quality import normalize

SPECS = [
    ('mineral-water', 'ミネラルウォーター', '💧', ['ミネラルウォーター 500ml 24本','天然水 2L 6本','天然水 500ml 48本'], 'per_liter','1Lあたり','per_bottle','1本あたり'),
    ('pasta', 'パスタ', '🍝', ['スパゲッティ 500g 6袋','スパゲッティ 1kg 5袋','スパゲッティ 500g'], 'per_100g','100gあたり','per_kg','1kgあたり'),
    ('granola', 'グラノーラ', '🥣', ['グラノーラ 750g','フルグラ 6袋','グラノーラ 500g'], 'per_100g','100gあたり','per_kg','1kgあたり'),
    ('retort-curry', 'レトルトカレー', '🍛', ['レトルトカレー 180g 10袋','レトルトカレー 200g 20食','レトルトカレー 10食','カレー レトルト 200g 10個','カレー レトルト 180g 30袋'], 'per_serving','1食あたり','per_100g','100gあたり'),
    ('bag-noodles', '袋麺', '🍜', ['サッポロ一番 5食 6袋','マルちゃん正麺 5食 6袋','チキンラーメン 5食 6袋','うまかっちゃん 5食 6袋'], 'per_serving','1食あたり',None,None),
    ('cup-noodles', 'カップ麺', '🍜', ['カップ麺 12個','カップヌードル 20個','カップラーメン 12個'], 'per_serving','1食あたり',None,None),
]
RULES = {
 'mineral-water': (r'ミネラルウォーター|天然水|ナチュラルウォーター|飲料水', r'炭酸|フレーバー|味付き|ジュース|お茶|緑茶|紅茶|水素|サプリ|サーバー|浄水|水筒|ボトルのみ|清涼飲料|スポーツドリンク'),
 'pasta': (r'スパゲ[ッテ]*ティ|スパゲティ|スパゲットーニ', r'ソース|調理済|冷凍|生パスタ|生麺|ギフト|ペンネ|マカロニ|フェットチーネ|ラザニア|そうめん|うどん'),
 'granola': (r'グラノーラ|フルグラ|グラノラ', r'プロテイン|サプリ|バー|クッキー|チョコレート菓子|詰め合わせ|コーンフレーク|オートミール'),
 'retort-curry': (r'レトルト.{0,12}カレー|カレー.{0,12}レトルト', r'ルー|ルウ|カレー粉|スープカレー|ご飯|ごはん|ライス|米飯|福袋|冷凍|詰め合わせ|カレーの素'),
 'bag-noodles': (r'袋麺|袋めん|袋ラーメン|袋入り|インスタントラーメン|即席袋|サッポロ一番|チキンラーメン|出前一丁|マルちゃん正麺|うまかっちゃん', r'カップ|どんぶり|スープのみ|麺のみ|替え玉|生麺|冷凍|ラーメン店|ご当地|詰め合わせ|乾麺|棒ラーメン|うどん|そば|焼きそば|焼そば|アソート'),
 'cup-noodles': (r'カップ麺|カップめん|カップラーメン|カップヌードル|どん兵衛|赤いきつね|緑のたぬき', r'袋麺|袋めん|袋ラーメン|ミニ|mini|小サイズ|詰め合わせ|福袋|ビッグ|BIG|大盛|デカ|メガ|特盛|ごつ盛り|うどん|そば|焼そば|焼きそば|コラボ|ギフトセット|賞味期限20'),
}
COMMON = re.compile(r'選べ|選択|よりどり|福袋|詰め合わせ|ふるさと納税|返礼品|定期|初回限定|会員限定|新規限定|お試し価格|アソート|より取り|容量不明', re.I)

def rejection(cid, title):
    t = normalize(title)
    if COMMON.search(t): return 'restricted_or_selectable_product'
    required, excluded = RULES[cid]
    if re.search(excluded, t, re.I): return 'wrong_product_type'
    if not re.search(required, t, re.I): return 'missing_category_evidence'
    return None


def parse(title, cid):
    """Parse a unique explicit pack chain; validate every remaining capacity/count."""
    t = normalize(title)
    if COMMON.search(t): return None
    volume = cid == 'mineral-water'
    count_only = cid in {'bag-noodles','cup-noodles'}
    amount_pattern = r'(?<![\w.])(\d+(?:\.\d+)?)\s*(ml|l)' if volume else r'(?<![\w.])(\d+(?:\.\d+)?)\s*(kg|g)'
    # Japanese characters are word characters; only prevent Latin/digit prefixes.
    amount_pattern = amount_pattern.replace(r'[\w.]',r'[A-Za-z0-9.]')
    amounts = list(re.finditer(amount_pattern, t, re.I))
    if not count_only and not amounts: return None
    count_units = r'(?:食|本|個|袋|パック|ケース|箱|セット)'
    tail = r'(?:\s*[)\]】]*\s*x\s*\d+\s*'+count_units+r'(?:入り|入)?){0,2}'
    chain = r'(?:\s*(?:[)\]】]*\s*x|\s+)\s*\d+\s*'+count_units+r'(?:入り|入)?'+tail+r')?'
    candidates = []
    if count_only:
        matches = list(re.finditer(r'(?<![\d.])(\d+)\s*(食|個)(?:入り|入)?'+tail, t, re.I))
    else:
        matches = list(re.finditer(amount_pattern+chain, t, re.I))
    for m in matches:
        evidence = m.group(0)
        if count_only:
            counts = [int(m.group(1))]
            counts += [int(v) for v in re.findall(r'(?:x|\s)\s*(\d+)\s*'+count_units, evidence[m.end(2)-m.start():], re.I)]
            amount = None
        else:
            amount = float(m.group(1)) * (1000 if m.group(2).lower() in {'kg','l'} else 1)
            counts = [int(v) for v in re.findall(r'(?:x|\s)\s*(\d+)\s*'+count_units, evidence[m.end(2)-m.start():], re.I)] or [1]
        count = 1
        for n in counts: count *= n
        if count <= 0 or count > 1000 or (amount is not None and amount <= 0): return None
        candidates.append((amount,count,counts,evidence))
    if not candidates: return None
    # First maximal chain; repeated totals may reinforce it, never introduce alternatives.
    amount,count,counts,evidence = max(candidates, key=lambda q: len(q[3]))
    if not count_only and any(a != amount or n != count for a,n,_,_ in candidates): return None
    if cid == 'retort-curry' and not 100 <= amount <= 350: return None
    if cid == 'mineral-water' and not 150 <= amount <= 5000: return None
    if cid == 'cup-noodles' and amounts:
        grams = {float(m.group(1))*(1000 if m.group(2).lower()=='kg' else 1) for m in amounts}
        if len(grams) != 1 or not 65 <= next(iter(grams)) <= 130: return None
    remainder = t.replace(evidence, ' ', 1)
    # Bare multipliers and missing units are unsafe; do not silently take an inner pack.
    if re.search(r'x\s*\d+', remainder, re.I): return None
    allowed = {count, *counts}
    visible = [int(v) for v in re.findall(r'(\d+)\s*'+count_units, remainder, re.I)]
    if any(v not in allowed for v in visible): return None
    if count_only:
        if any(n not in allowed for _,n,_,_ in candidates): return None
        # Bag noodles need explicit serving evidence rather than bags alone.
        return {'count':count,'component_counts':counts,'confidence':0.99,'evidence':evidence}
    key = 'volume_ml' if volume else 'weight_g'
    return {'count':count,'component_counts':counts,'unit_'+key:amount,'total_'+key:amount*count,'confidence':0.99,'evidence':evidence}


def categories():
    out=[]
    for cid,name,emoji,queries,primary,label,secondary,slabel in SPECS:
        out.append(dict(id=cid,name=name,emoji=emoji,queries=queries,primary=primary,primary_label=label,secondary=secondary,secondary_label=slabel,intro=f'{name}の容量・食数を確定し、{label}で比べます。',filter_small='少量',filter_large='まとめ買い',guide=['内容量とセット数を一意に確認できる商品だけを掲載します。','送料込みの商品と送料別・送料不明の商品を分けています。','種類・賞味期限・保管場所は購入前に販売ページで確認してください。']))
    return out
