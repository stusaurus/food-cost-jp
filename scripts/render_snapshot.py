"""Render an offline preview without fetching, rewriting or redating product data."""
import json
from datetime import datetime
from pathlib import Path
import shutil

import build_site as build


def main():
    snapshot = json.loads(Path('data/products.json').read_text())
    updated = datetime.fromisoformat(snapshot['generated_at'])
    results = {key: (value['included'], value['shipping_unknown'])
               for key, value in snapshot['categories'].items()}
    build.ACTIVE_CATEGORY_IDS = {c['id'] for c in build.active_categories(results)}
    output = build.OUT
    output.mkdir(exist_ok=True)
    shutil.copytree('assets', output / 'assets', dirs_exist_ok=True)
    shutil.copytree('data', output / 'data', dirs_exist_ok=True)
    guides = build.GUIDE_SPECS + build.eligible_auto_guides(results)
    pages = {'index.html': build.home_page(results, updated, guides),
             'deals/index.html': build.deals_page(results, updated),
             'saved/index.html': build.saved_watch_page(updated)}
    for category in build.CATEGORIES:
        included, other = results.get(category['id'], ([], []))
        pages[f"categories/{category['id']}/index.html"] = build.category_page(category, included, other, updated)
    for spec in guides:
        category = next(c for c in build.CATEGORIES if c['id'] == spec['category_id'])
        pages[f"guides/{spec['slug']}/index.html"] = build.guide_page(spec, category, results.get(category['id'], ([], []))[0], updated)
    for name, content in pages.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for name in ['sitemap.xml', 'robots.txt']:
        shutil.copyfile(name, output / name)
    print(f'Rendered {len(pages)} pages with unchanged product data ({snapshot["generated_at"]})')


if __name__ == '__main__':
    main()
