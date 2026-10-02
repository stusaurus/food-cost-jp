"""Fetch live candidate data before enabling any new public category."""
import json
from pathlib import Path
import build_site as b
from new_food import categories, parse, rejection
from product_quality import quantity_conflict
old_parse, old_rejection, old_prices = b.parse_quantity, b.category_rejection, b.unit_prices
ids = {c['id'] for c in categories()}
b.parse_quantity = lambda title,cid: parse(title,cid) if cid in ids else old_parse(title,cid)
b.category_rejection = lambda cid,title: rejection(cid,title) if cid in ids else old_rejection(cid,title)
def prices(price,q,cid):
    if cid == 'mineral-water': return dict(per_liter=price/(q['total_volume_ml']/1000),per_bottle=price/q['count'])
    if cid in {'pasta','granola'}: return dict(per_100g=price/(q['total_weight_g']/100),per_kg=price/(q['total_weight_g']/1000))
    if cid == 'retort-curry': return dict(per_serving=price/q['count'],per_100g=price/(q['total_weight_g']/100))
    if cid in ids: return dict(per_serving=price/q['count'])
    return old_prices(price,q,cid)
b.unit_prices = prices
report = {}
for c in categories():
    included, other, audit = b.collect(c)
    report[c['id']] = dict(category=c,included=included,shipping_unknown=other,audit=audit)
    print('PROBE',c['id'],len(included),len(other),json.dumps(audit,ensure_ascii=False))
Path('candidate-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
