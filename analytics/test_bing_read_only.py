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
