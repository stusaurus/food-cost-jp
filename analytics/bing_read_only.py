"""Read-only Bing Webmaster API: exact site, no credentials or raw search queries in output."""
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError

SITE = "https://stusaurus.github.io/food-cost-jp/"
API = "https://ssl.bing.com/webmaster/api.svc/json/"
METHODS = ("GetRankAndTrafficStats", "GetPageStats", "GetCrawlStats", "GetFeeds")
CRAWL_FIELDS = {"InIndex": "in_index", "CrawledPages": "crawled_pages", "CrawlErrors": "crawl_errors", "BlockedByRobotsTxt": "blocked_by_robots", "Code4xx": "http_4xx", "Code5xx": "http_5xx"}
FEED_URL = SITE + "sitemap.xml"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(method, key):
    if method not in METHODS:
        raise ValueError("unsupported method")
    url = API + method + "?" + urlencode({"siteUrl": SITE, "apikey": key})
    with build_opener(NoRedirect()).open(Request(url, headers={"Accept":"application/json"}), timeout=30) as response:
        return json.load(response)

def parse_date(value):
    match = re.fullmatch(r"/Date\((-?\d+)([+-]\d{4})?\)/", value)
    if not match:
        raise ValueError("invalid date")
    offset = match[2]
    zone = dt.timezone.utc
    if offset:
        minutes = int(offset[1:3])*60 + int(offset[3:5])
        zone = dt.timezone(dt.timedelta(minutes=minutes if offset[0] == "+" else -minutes))
    return dt.datetime.fromtimestamp(int(match[1])/1000, zone).date().isoformat()

def metric(row, name):
    value = row[name]
    if type(value) is not int or value < 0:
        raise ValueError("invalid metric")
    return value

def parse(payload, method):
    if method not in METHODS or not isinstance(payload, dict) or not isinstance(payload.get("d"), list):
        raise ValueError("unexpected response")
    rows = []
    for r in payload["d"]:
        if method == "GetCrawlStats":
            rows.append({"date": parse_date(r["Date"]), **{
                label: metric(r, field) for field, label in CRAWL_FIELDS.items()
            }})
            continue
        if method == "GetFeeds":
            if r["Url"] != FEED_URL:
                continue
            status = r["Status"]
            if not isinstance(status, str) or not re.fullmatch(r"[A-Za-z0-9 _-]{1,60}", status):
                raise ValueError("invalid sitemap status")
            row = {"url": FEED_URL, "status": status, "url_count": metric(r, "UrlCount")}
            for field, label in (("LastCrawled", "last_crawled"), ("Submitted", "submitted")):
                value = r.get(field)
                row[label] = parse_date(value) if value is not None else None
            rows.append(row)
            continue
        item = {"date":parse_date(r["Date"]), "clicks":metric(r,"Clicks"), "impressions":metric(r,"Impressions")}
        if method == "GetPageStats":
            page = r["Query"]
            if not isinstance(page,str) or not page.startswith(SITE):
                raise ValueError("unexpected page scope")
            if not re.fullmatch(re.escape(SITE)+r"(?:[a-z0-9-]+/)*(?:index\.html)?",page):
                continue
            item["page"] = page
        rows.append(item)
    return {"status":"OBSERVED_ROWS" if rows else "NO_OBSERVED_ROWS","rows":rows or None}


def run(key=None, request=fetch):
    result = {"site":SITE,"source":"Bing Webmaster API","missing_is_zero":False,
              "note":"RankAndTrafficStats includes Bing search verticals; page rows can be aggregated over provider-defined periods. Do not sum across reports. InIndex is a dated site-level count, not a URL-level verdict. Missing sitemap rows do not prove non-registration."}
    for method in METHODS:
        if not key:
            result[method] = {"status":"NOT_CONFIGURED","rows":None}
            continue
        try:
            result[method] = parse(request(method,key),method)
        except HTTPError as exc:
            result[method] = {"status":"UNAVAILABLE","reason":"HTTP_"+str(exc.code),"rows":None}
        except Exception:
            result[method] = {"status":"UNAVAILABLE","reason":"READ_OR_SCHEMA_FAILED","rows":None}
    return result

if __name__ == "__main__":
    report = run(os.environ.get("BING_WEBMASTER_API_KEY"))
    path = Path("audit-results/bing/report.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if any(report[m]["status"] not in ("OBSERVED_ROWS","NO_OBSERVED_ROWS") for m in METHODS):
        raise SystemExit(1)
