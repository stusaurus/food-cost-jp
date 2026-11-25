import unittest
from bing_read_only import SITE, parse, run

class BingReportTests(unittest.TestCase):
    def test_missing_credentials_are_unknown(self):
        r=run()
        self.assertEqual(r["GetPageStats"]["status"],"NOT_CONFIGURED")
        self.assertIsNone(r["GetPageStats"]["rows"])
    def test_daily_metrics(self):
        r=parse({"d":[{"Date":"/Date(1795474800000+0000)/","Clicks":2,"Impressions":10}]},"GetRankAndTrafficStats")
        self.assertEqual(r["rows"][0]["clicks"],2)
        self.assertEqual(r["rows"][0]["impressions"],10)
    def test_pages_reject_other_site(self):
        with self.assertRaises(ValueError):
            parse({"d":[{"Date":"/Date(1795474800000+0000)/","Clicks":1,"Impressions":2,"Query":"https://stusaurus.github.io/daily-cost-jp/"}]},"GetPageStats")
    def test_empty_rows_unknown(self):
        self.assertIsNone(parse({"d":[]},"GetPageStats")["rows"])
    def test_credentials_never_in_error(self):
        def fail(method,key):
            raise RuntimeError(key)
        r=run("private-test-key",fail)
        self.assertNotIn("private-test-key",str(r))
        self.assertEqual(r["GetPageStats"]["status"],"UNAVAILABLE")

    def test_crawl_stats_preserve_actual_zero_and_missing(self):
        row = {"Date":"/Date(1795474800000+0000)/","InIndex":7,"CrawledPages":11,
               "CrawlErrors":0,"BlockedByRobotsTxt":0,"Code4xx":1,"Code5xx":0}
        result = parse({"d":[row]}, "GetCrawlStats")
        self.assertEqual(result["rows"][0]["in_index"], 7)
        self.assertEqual(result["rows"][0]["crawl_errors"], 0)
        self.assertIsNone(parse({"d":[]}, "GetCrawlStats")["rows"])
        del row["InIndex"]
        with self.assertRaises(KeyError):
            parse({"d":[row]}, "GetCrawlStats")

    def test_only_exact_food_sitemap_is_reported(self):
        row = {"Url": SITE+"sitemap.xml","Status":"Success","UrlCount":35,
               "LastCrawled":"/Date(1795474800000+0000)/"}
        other = dict(row, Url="https://stusaurus.github.io/kyo-bodo-jp/sitemap.xml")
        result = parse({"d":[other,row]}, "GetFeeds")
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["url_count"],35)
        self.assertIsNone(parse({"d":[other]},"GetFeeds")["rows"])
        self.assertEqual(run()["GetCrawlStats"]["status"],"NOT_CONFIGURED")
