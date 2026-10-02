"""Replay current rules against the saved API snapshot without redating prices."""
import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import build_site as build
from price_history import apply_price_history, load_price_history

def main():
    build.GA_ID = os.environ.get('GA_MEASUREMENT_ID', 'G-GFVSZ8YDQ5')
    snapshot = json.loads(Path('data/products.json').read_text())
    updated = datetime.fromisoformat(snapshot['generated_at'])
    results, excluded, corrected = {}, [], []
    history = load_price_history(Path('data/price-history.json'))
    for c in build.CATEGORIES:
        payload = snapshot['categories'][c['id']]
        for key in ('included','shipping_unknown'):
            accepted = []
            for x in payload[key]:
                raw = dict(itemName=x['raw_name'],itemPrice=x['price'],itemCode=x['id'],shopName=x['shop'],affiliateUrl=x['url'],postageFlag=0 if key=='included' else 1,mediumImageUrls=[x['image']])
                item, reason = build.normalize_item_with_reason(raw,c)
                if reason:
                    excluded.append((c['id'],x['id'],reason)); continue
                if item['quantity'] != x['quantity']: corrected.append((c['id'],x['id']))
                accepted.append(item)
            accepted.sort(key=lambda x:(x['unit_prices'][c['primary']],x['price']))
            payload[key] = accepted
        results[c['id']] = (payload['included'],payload['shipping_unknown'])
        apply_price_history(history,c,payload['included']+payload['shipping_unknown'],updated.date())
    output=build.OUT;output.mkdir(exist_ok=True)
    shutil.copytree('assets',output/'assets',dirs_exist_ok=True)
    shutil.copytree('data',output/'data',dirs_exist_ok=True)
    (output/'data/products.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
    build.render_pages(results,updated)
    print(f'Replayed snapshot at original timestamp {snapshot["generated_at"]}; exclusions={excluded}; quantity corrections={corrected}')
if __name__=='__main__': main()
