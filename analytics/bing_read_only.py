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
METHODS = ("GetRankAndTrafficStats", "GetPageStats")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(method, key):
    if method not in METHODS:
        raise ValueError("unsupported method")
    url = API + method + "?" + urlencode({"siteUrl": SITE, "apikey": key})
    with build_opener(NoRedirect()).open(Request(url, headers={"Accept":"application/json"}), timeout=30) as response:
        return json.load(response)

def parse(payload, method):
    if method not in METHODS or not isinstance(payload, dict) or not isinstance(payload.get("d"), list):
        raise ValueError("unexpected response")
    rows = []
    for r in payload["d"]:
        clicks, impressions = r["Clicks"], r["Impressions"]
        if type(clicks) is not int or type(impressions) is not int or min(clicks, impressions) < 0:
            raise ValueError("invalid metrics")
        match = re.fullmatch(r"/Date\((-?\d+)([+-]\d{4})?\)/", r["Date"])
        if not match:
            raise ValueError("invalid date")
        offset = match[2]
        zone = dt.timezone.utc
        if offset:
            minutes = int(offset[1:3])*60 + int(offset[3:5])
            zone = dt.timezone(dt.timedelta(minutes=minutes if offset[0] == "+" else -minutes))
        day = dt.datetime.fromtimestamp(int(match[1])/1000, zone).date().isoformat()
        item = {"date":day,"clicks":clicks,"impressions":impressions}
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
              "note":"RankAndTrafficStats includes Bing search verticals; page rows can be aggregated over provider-defined periods. Do not sum across reports."}
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
