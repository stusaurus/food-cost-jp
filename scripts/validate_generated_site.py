"""Fail closed on the generated site before publishing it to GitHub Pages."""
from __future__ import annotations

import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SITE_URL = "https://stusaurus.github.io/food-cost-jp/"
MIN_ITEMS = 3
LEGACY_IDS = {"pack-rice", "rice", "carbonated-water", "oatmeal"}
MAX_UNIT_PRICE = {
    "per_serving": 5000,
    "per_100g": 5000,
    "per_kg": 50000,
    "per_liter": 10000,
    "per_bottle": 5000,
}

class PageAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = []
        self.robots = []
        self.h1 = 0
        self.jsonld = 0
        self.links = []
        self.images_missing_alt = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "canonical" in a.get("rel", "").split():
            self.canonical.append(a.get("href", ""))
        if tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots.append(a.get("content", ""))
        if tag == "h1":
            self.h1 += 1
        if tag == "script" and a.get("type") == "application/ld+json":
            self.jsonld += 1
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "img" and "alt" not in a:
            self.images_missing_alt += 1

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def eligible_categories(data):
    return {
        cid for cid, payload in data["categories"].items()
        if len(payload.get("included", [])) >= MIN_ITEMS
    }

def prune_ineligible(site, eligible):
    root = site / "categories"
    if not root.exists():
        return
    for child in root.iterdir():
        if child.is_dir() and child.name not in eligible:
            shutil.rmtree(child)

def validate_products(current, previous=None):
    errors = []
    for cid, payload in current["categories"].items():
        items = payload.get("included", [])
        if cid in LEGACY_IDS and len(items) < MIN_ITEMS:
            errors.append(f"{cid}: core category has only {len(items)} safe items")
        ids = [x.get("id") for x in items]
        if len(ids) != len(set(ids)):
            errors.append(f"{cid}: duplicate product ids")
        for item in items:
            if not item.get("id") or not item.get("name"):
                errors.append(f"{cid}: product missing id/name")
            url = item.get("url", "")
            host = (urlparse(url).hostname or "").lower()
            if host != "hb.afl.rakuten.co.jp":
                errors.append(f"{cid}: non-affiliate or unexpected product URL for {item.get('id')}")
            prices = item.get("unit_prices") or {}
            if not prices:
                errors.append(f"{cid}: missing unit prices for {item.get('id')}")
            for key, value in prices.items():
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    errors.append(f"{cid}: invalid {key} for {item.get('id')}")
                    continue
                ceiling = MAX_UNIT_PRICE.get(key, 100000)
                if not math.isfinite(value) or value <= 0 or value > ceiling:
                    errors.append(f"{cid}: abnormal {key}={value} for {item.get('id')}")
    if previous:
        for cid, old in previous.get("categories", {}).items():
            old_n = len(old.get("included", []))
            new_n = len(current.get("categories", {}).get(cid, {}).get("included", []))
            if old_n >= 5 and new_n < max(MIN_ITEMS, math.ceil(old_n * 0.4)):
                errors.append(f"{cid}: safe item count collapsed {old_n} -> {new_n}")
    return errors

def expected_url_for(path, site):
    rel = path.relative_to(site)
    if rel.as_posix() == "index.html":
        return SITE_URL
    return SITE_URL + rel.parent.as_posix().rstrip("/") + "/"

def validate_pages(site, eligible):
    errors = []
    pages = [site / "index.html", site / "deals/index.html"]
    pages += [site / f"categories/{cid}/index.html" for cid in sorted(eligible)]
    pages += sorted((site / "guides").glob("*/index.html")) if (site / "guides").exists() else []
    for page in pages:
        if not page.exists():
            errors.append(f"missing important page: {page}")
            continue
        parser = PageAudit()
        parser.feed(page.read_text(encoding="utf-8"))
        expected = expected_url_for(page, site)
        if parser.canonical != [expected]:
            errors.append(f"{page}: canonical {parser.canonical!r}, expected {expected}")
        if parser.h1 != 1:
            errors.append(f"{page}: expected exactly one H1, got {parser.h1}")
        if any("noindex" in x.lower() for x in parser.robots):
            errors.append(f"{page}: indexable page contains noindex")
        if parser.images_missing_alt:
            errors.append(f"{page}: {parser.images_missing_alt} images missing alt")
        if not parser.jsonld:
            errors.append(f"{page}: missing JSON-LD")
    return errors, pages

def validate_sitemap(site, pages):
    errors = []
    path = site / "sitemap.xml"
    if not path.exists():
        return ["missing sitemap.xml"]
    root = ET.parse(path).getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    actual = {x.text for x in root.findall("s:url/s:loc", ns)}
    expected = {expected_url_for(p, site) for p in pages}
    if actual != expected:
        errors.append("sitemap URLs do not exactly match indexable generated pages")
        errors.append("missing from sitemap: " + ", ".join(sorted(expected - actual)))
        errors.append("unexpected in sitemap: " + ", ".join(sorted(actual - expected)))
    return errors

def main():
    site = Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    current = load(site / "data/products.json")
    previous_path = Path("data/products.json")
    previous = load(previous_path) if previous_path.exists() else None
    eligible = eligible_categories(current)
    prune_ineligible(site, eligible)
    errors = validate_products(current, previous)
    page_errors, pages = validate_pages(site, eligible)
    errors += page_errors
    errors += validate_sitemap(site, pages)
    robots = (site / "robots.txt").read_text(encoding="utf-8") if (site / "robots.txt").exists() else ""
    if "Allow: /" not in robots or SITE_URL + "sitemap.xml" not in robots:
        errors.append("robots.txt does not expose the site and sitemap correctly")
    if errors:
        print("GENERATED SITE QUALITY GATE FAILED")
        for error in errors:
            if error:
                print("-", error)
        raise SystemExit(1)
    counts = {cid: len(v.get("included", [])) for cid, v in current["categories"].items()}
    print("GENERATED SITE QUALITY GATE PASSED")
    print("eligible_categories=", ",".join(sorted(eligible)))
    print("safe_item_counts=", json.dumps(counts, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
