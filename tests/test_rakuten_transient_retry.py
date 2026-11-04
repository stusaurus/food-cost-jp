import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from test_marche import build


class ApiResponse:
    def __init__(self, data):
        self.body = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def http_error(code):
    return urllib.error.HTTPError(
        "https://example.invalid/api", code, "temporary_or_permanent_error", {}, None
    )


class RakutenTransientRetryTests(unittest.TestCase):
    def test_single_503_then_valid_exact_response(self):
        row = {"itemCode": "test:1000", "itemName": "example"}
        with patch.object(build.urllib.request, "urlopen", side_effect=[http_error(503), ApiResponse({"items": [row]})]) as fetch, \
             patch.object(build.time, "sleep") as delay:
            self.assertEqual(build.fetch("rice 10kg"), [row])
        self.assertEqual(fetch.call_count, 2)
        delay.assert_called_once_with(1.5)

    def test_transient_502_and_504_have_same_bounded_recovery(self):
        for code in (502, 504):
            with self.subTest(code=code), \
                 patch.object(build.urllib.request, "urlopen", side_effect=[http_error(code), ApiResponse({"Items": []})]) as fetch, \
                 patch.object(build.time, "sleep") as delay:
                self.assertEqual(build.fetch("pack rice"), [])
                self.assertEqual(fetch.call_count, 2)
                delay.assert_called_once_with(1.5)

    def test_retries_stop_and_fail_closed_after_three_errors(self):
        with patch.object(build.urllib.request, "urlopen", side_effect=[http_error(503)] * 3) as fetch, \
             patch.object(build.time, "sleep") as delay:
            with self.assertRaises(urllib.error.HTTPError) as err:
                build.fetch("rice 10kg")
        self.assertEqual(err.exception.code, 503)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual([c.args[0] for c in delay.call_args_list], [1.5, 3.0])

    def test_auth_and_rate_limit_do_not_retry(self):
        for code in (400, 401, 403, 429):
            with self.subTest(code=code), \
                 patch.object(build.urllib.request, "urlopen", side_effect=[http_error(code)]) as fetch, \
                 patch.object(build.time, "sleep") as delay:
                with self.assertRaises(urllib.error.HTTPError) as err:
                    build.fetch("rice 10kg")
                self.assertEqual(err.exception.code, code)
                self.assertEqual(fetch.call_count, 1)
                delay.assert_not_called()

    def test_successful_empty_payload_is_not_retried_or_fabricated(self):
        with patch.object(build.urllib.request, "urlopen", return_value=ApiResponse({"items": []})) as fetch, \
             patch.object(build.time, "sleep") as delay:
            self.assertEqual(build.fetch("rice 10kg"), [])
        self.assertEqual(fetch.call_count, 1)
        delay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
