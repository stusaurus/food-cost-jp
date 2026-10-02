"""Read-only, fail-closed product, crawl and publication gate for Pages."""
from __future__ import annotations
import json
import math
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote, parse_qs
import build_site as build
from product_quality import product_fingerprint, quantity_signature

SITE_URL = build.SITE_URL
MIN_ITEMS = build.MIN_CATEGORY_ITEMS
MAX_UNIT_PRICE = {'per_serving': 5000, 'per_100g': 5000, 'per_kg': 50000, 'per_liter': 10000, 'per_bottle': 5000}

class PageAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical, self.robots, self.links, self.assets, self.schemas = [], [], [], [], []
        self.ids, self.h1, self.title, self.description = set(), 0, '', ''
        self.image_errors, self.affiliate_errors, self.schema_errors = [], [], []
        self._json, self._title, self._buffer = False, False, ''
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        if tag == 'link' and 'canonical' in a.get('rel', '').split(): self.canonical.append(a.get('href', ''))
        if tag == 'meta' and a.get('name', '').lower() == 'robots': self.robots.append(a.get('content', ''))
        if tag == 'meta' and a.get('name') == 'description': self.description = a.get('content', '')
        if tag == 'h1': self.h1 += 1
        if tag == 'title': self._title = True
        if tag == 'script' and a.get('type') == 'application/ld+json': self._json, self._buffer = True, ''
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
            if urlparse(a['href']).hostname == 'hb.afl.rakuten.co.jp':
                required = ('data-affiliate', 'data-position', 'data-category', 'data-product-id', 'data-metric', 'data-unit-price', 'data-shipping')
                if not all(a.get(k) for k in required) or a.get('target') != '_blank' or not {'sponsored','nofollow','noopener'} <= set(a.get('rel','').split()):
                    self.affiliate_errors.append(a['href'])
        if tag == 'img':
            if 'alt' not in a or not a.get('width') or not a.get('height'): self.image_errors.append(a.get('src',''))
            self.assets.append(a.get('src', ''))
    def handle_data(self, data):
        if self._title: self.title += data
        if self._json: self._buffer += data
    def handle_endtag(self, tag):
        if tag == 'title': self._title = False
        if tag == 'script' and self._json:
            try:
                schema = json.loads(self._buffer)
                if not isinstance(schema, dict) or schema.get('@context') != 'https://schema.org' or not schema.get('@type'):
                    raise ValueError('missing schema type/context')
                self.schemas.append(schema)
            except (ValueError, TypeError): self.schema_errors.append('invalid JSON-LD')
            self._json = False

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def eligible_categories(data):
    return {cid for cid,p in data['categories'].items() if len(p.get('included',[])) >= MIN_ITEMS}

def validate_products(current, previous=None):
    errors = []
    definitions = {c['id']: c for c in build.CATEGORIES}
    if set(current.get('categories', {})) != set(definitions): errors.append('category definitions missing or unexpected')
    for cid, payload in current.get('categories', {}).items():
        if cid not in definitions: continue
        c = definitions[cid]
        if cid in build.LEGACY_IDS and len(payload.get('included', [])) < MIN_ITEMS: errors.append(f'{cid}: core category below publication floor')
        audit = payload.get('quality_audit', {})
        if audit.get('fetch_errors', 0): errors.append(f'{cid}: API query failed; retain previous published site')
        ids, fingerprints = set(), set()
        for bucket in ('included','shipping_unknown'):
            items = payload.get(bucket, [])
            units = []
            for x in items:
                prefix = f'{cid}/{x.get("id")}'
                if not x.get('id') or x['id'] in ids: errors.append(prefix + ': missing/duplicate product id')
                ids.add(x.get('id'))
                expected_shipping = bucket == 'included'
                if bool(x.get('postage_included')) != expected_shipping or x.get('shipping_status') != ('included' if expected_shipping else 'extra_or_unknown'):
                    errors.append(prefix + ': shipping classification mismatch')
                url = urlparse(x.get('url',''))
                target = parse_qs(url.query).get('pc', [''])[0]
                target_url = urlparse(target)
                if url.scheme != 'https' or url.hostname != 'hb.afl.rakuten.co.jp' or not url.path.startswith('/hgc/') or target_url.hostname != 'item.rakuten.co.jp' or target_url.scheme != 'https':
                    errors.append(prefix + ': invalid affiliate destination')
                raw = dict(itemName=x.get('raw_name'), itemPrice=x.get('price'), itemCode=x.get('id'), affiliateUrl=x.get('url'), postageFlag=0 if expected_shipping else 1)
                normalized, reason = build.normalize_item_with_reason(raw, c)
                if reason:
                    errors.append(prefix + ': unsafe stored product: ' + reason)
                    continue
                if quantity_signature(cid,normalized['quantity']) != quantity_signature(cid,x.get('quantity',{})):
                    errors.append(prefix + ': quantity disagrees with raw title')
                prices = x.get('unit_prices',{})
                if set(prices) != set(normalized['unit_prices']): errors.append(prefix + ': missing comparison units')
                for key,value in prices.items():
                    if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 < value <= MAX_UNIT_PRICE.get(key,100000):
                        errors.append(prefix + ': abnormal unit price'); continue
                    if not math.isclose(value,normalized['unit_prices'].get(key,0),rel_tol=1e-8,abs_tol=1e-6): errors.append(prefix + ': incorrect unit calculation')
                units.append(prices.get(c['primary'],0))
                fingerprint = (x.get('shop'),product_fingerprint(x.get('name','')),quantity_signature(cid,x.get('quantity',{})),bucket)
                if fingerprint in fingerprints: errors.append(prefix + ': practical duplicate')
                fingerprints.add(fingerprint)
            if units != sorted(units): errors.append(cid + ': ranking is not ordered by unit price')
    if previous:
        for cid,old in previous.get('categories',{}).items():
            n = len(old.get('included',[])); new = current.get('categories',{}).get(cid,{})
            m = len(new.get('included',[]))
            if n >= MIN_ITEMS and (m < MIN_ITEMS or m < math.ceil(n*.4)): errors.append(f'{cid}: safe inventory collapsed {n} -> {m}')
            before = old.get('quality_audit',{}); after = new.get('quality_audit',{})
            def failure_rate(a):
                return sum(a.get('reasons',{}).get(k,0) for k in ('ambiguous_quantity','set_count_conflict')) / max(1,a.get('fetched',0))
            if after.get('fetched',0) >= 30 and before.get('fetched',0) >= 30 and failure_rate(after) > .8 and failure_rate(after) > failure_rate(before)+.25:
                errors.append(f'{cid}: quantity parsing failure rate surged')
    return errors

def expected_url_for(path, site):
    rel = path.relative_to(site).as_posix()
    return SITE_URL + (rel[:-10] if rel.endswith('index.html') else rel)

def local_path(url, site):
    parsed = urlparse(url)
    if parsed.netloc != urlparse(SITE_URL).netloc or not parsed.path.startswith(urlparse(SITE_URL).path): return None
    rel = unquote(parsed.path[len(urlparse(SITE_URL).path):])
    if '..' in Path(rel).parts: return None
    return site / (rel+'index.html' if not rel or rel.endswith('/') else rel)

def validate_pages(site, eligible):
    errors, audited = [], {}
    important = ['index.html','deals/index.html','saved/index.html','404.html'] + [f'categories/{cid}/index.html' for cid in eligible]
    for name in important:
        if not (site/name).exists(): errors.append('missing important page: '+name)
    for page in sorted(site.rglob('*.html')):
        parser = PageAudit(); parser.feed(page.read_text(encoding='utf-8')); audited[page] = parser
        expected = expected_url_for(page,site)
        if parser.h1 != 1 or not parser.title or not parser.description: errors.append(f'{page}: missing/duplicate H1, title or description')
        if len(parser.canonical) != 1 or not parser.canonical[0].startswith(SITE_URL): errors.append(f'{page}: invalid canonical')
        if parser.image_errors: errors.append(f'{page}: images need alt/dimensions')
        if parser.affiliate_errors: errors.append(f'{page}: untracked/unsafe affiliate links')
        if parser.schema_errors: errors.append(f'{page}: malformed structured data')
        if '/categories/' in expected and page.parent.name not in eligible and not any('noindex' in r for r in parser.robots): errors.append(f'{page}: sparse category is indexable')
        if page.name == '404.html' or page.parent.name == 'saved':
            if not any('noindex' in r for r in parser.robots): errors.append(f'{page}: utility must be noindex')
        elif not parser.schemas: errors.append(f'{page}: missing structured data')
    indexable = {p for p,a in audited.items() if not any('noindex' in r.lower() for r in a.robots) and a.canonical == [expected_url_for(p,site)]}
    titles = {}
    graph = {p:set() for p in audited}
    for page,a in audited.items():
        for link in a.links+a.assets+a.canonical:
            url = urljoin(expected_url_for(page,site),link); target = local_path(url,site)
            if target is None: continue
            if not target.exists(): errors.append(f'{page}: broken internal link/asset {link}'); continue
            if target in audited and link in a.links:
                graph[page].add(target)
                fragment = unquote(urlparse(url).fragment)
                if fragment and fragment not in audited[target].ids: errors.append(f'{page}: missing anchor {link}')
        if page in indexable:
            if a.title in titles: errors.append(f'{page}: duplicate title with {titles[a.title]}')
            titles[a.title]=page
    seen, pending = set(), [site/'index.html']
    while pending:
        p = pending.pop()
        if p in seen: continue
        seen.add(p); pending.extend(graph.get(p,set())-seen)
    for p in indexable-seen: errors.append(f'{p}: orphan indexable page')
    return errors, sorted(indexable)

def validate_sitemap(site, pages):
    try:
        root = ET.parse(site/'sitemap.xml').getroot()
    except (OSError,ET.ParseError): return ['missing/malformed sitemap.xml']
    ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls=[x.text for x in root.findall('s:url/s:loc',ns)]
    expected={expected_url_for(p,site) for p in pages}
    if len(urls) != len(set(urls)): return ['duplicate sitemap URLs']
    if set(urls) != expected: return ['sitemap differs from canonical indexable pages: '+str(set(urls)^expected)]
    return []

def audit_site(site, previous=None):
    data=load(site/'data/products.json')
    errors=validate_products(data,previous)
    page_errors,pages=validate_pages(site,eligible_categories(data)); errors+=page_errors
    errors+=validate_sitemap(site,pages)
    results={c:(p['included'],p['shipping_unknown']) for c,p in data['categories'].items()}
    published,aliases=build.publication_guides(results)
    expected={SITE_URL,SITE_URL+'deals/'}|{SITE_URL+f'categories/{c}/' for c in eligible_categories(data)}|{SITE_URL+f'guides/{s["slug"]}/' for s in published}
    if {expected_url_for(p,site) for p in pages} != expected: errors.append('publication inventory and indexable pages disagree')
    for slug,target in aliases.items():
        a=PageAudit();a.feed((site/f'guides/{slug}/index.html').read_text())
        if a.canonical != [SITE_URL+f'guides/{target}/']: errors.append(slug+': duplicate guide canonical incorrect')
    robots=(site/'robots.txt').read_text() if (site/'robots.txt').exists() else ''
    if 'Allow: /' not in robots or 'Disallow: /' in robots or SITE_URL+'sitemap.xml' not in robots: errors.append('robots blocks crawling or omits sitemap')
    return dict(passed=not errors,errors=errors,indexable_pages=len(pages),canonical_aliases=aliases,safe_item_counts={c:len(p['included']) for c,p in data['categories'].items()})

def main():
    site=Path(sys.argv[1] if len(sys.argv)>1 else 'site')
    prior=Path('data/products.json')
    report=audit_site(site,load(prior) if prior.exists() else None)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__': main()
