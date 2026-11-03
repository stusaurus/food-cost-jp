"""Build-workflow contract: stale snapshots must never push generated HTML."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FoodPublicationContractTest(unittest.TestCase):
    def test_main_freshness_guard_is_run_twice(self):
        yaml = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("id: release_preflight", yaml)
        self.assertIn("run: python scripts/check_publish_freshness.py", yaml)
        self.assertIn("if: steps.release_preflight.outputs.publish == 'true'", yaml)
        self.assertIn('current_main="$(git ls-remote origin refs/heads/main', yaml)
        self.assertIn('if [[ "$current_main" != "$GITHUB_SHA" ]]; then', yaml)

    def test_no_stale_or_failed_push_is_misreported_as_published(self):
        yaml = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        before_push, after_push = yaml.split("git push origin HEAD:main", 1)
        self.assertIn('echo "published=false" >> "$GITHUB_OUTPUT"', before_push)
        self.assertIn('echo "published=true" >> "$GITHUB_OUTPUT"', after_push)
        self.assertNotIn("git push --force", yaml)
        self.assertIn("set -euo pipefail", yaml)

    def test_indexnow_only_after_new_publication(self):
        yaml = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn(
            "- name: Submit sitemap URLs to IndexNow\n"
            "        if: steps.publish_site.outputs.published == 'true'",
            yaml,
        )

    def test_daily_schedule_still_runs_and_main_source_changes_trigger(self):
        yaml = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 20 * * *"', yaml)
        self.assertIn('- "scripts/**"', yaml)
        self.assertIn('branches: [main]', yaml)


if __name__ == "__main__":
    unittest.main()
