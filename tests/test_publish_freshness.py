"""Regression tests for protecting generated-food-site publication."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import os
import tempfile
import subprocess

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_publish_freshness.py"
spec = importlib.util.spec_from_file_location("check_publish_freshness", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FoodReleaseFreshnessTest(unittest.TestCase):
    def test_equal_current_main_can_publish(self):
        self.assertTrue(module.eligible_for_publication("a" * 40, "a" * 40))

    def test_superseded_build_is_skipped(self):
        self.assertFalse(module.eligible_for_publication("a" * 40, "b" * 40))

    def test_invalid_and_missing_sha_fails_closed(self):
        for a, b in [
            ("", "a" * 40), ("a" * 40, ""), ("a" * 39, "b" * 40),
            ("A" * 40, "a" * 40), ("x" * 40, "b" * 40)
        ]:
            with self.subTest(run=a[:4], main=b[:4]):
                with self.assertRaises(ValueError):
                    module.eligible_for_publication(a, b)

    def test_unreadable_remote_is_error_not_approval(self):
        with patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 25)):
            with self.assertRaises(subprocess.TimeoutExpired):
                module.fetch_main_sha()

    def test_github_output_and_superseded_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "outputs"
            with patch.dict(os.environ, {"GITHUB_SHA": "a"*40, "GITHUB_OUTPUT": str(output)}):
                with patch.object(module, "fetch_main_sha", return_value="b"*40):
                    self.assertEqual(module.main(), 0)
            self.assertIn("publish=false", output.read_text(encoding="utf-8"))
            self.assertIn("main_sha=" + "b"*40, output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
