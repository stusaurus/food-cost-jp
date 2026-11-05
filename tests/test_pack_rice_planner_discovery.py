"""Show the existing purchase planner only when its guide is published."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_site import category_guide_navigation


class PlannerDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.category = {"id": "pack-rice", "name": "パックご飯"}
        self.guide = {"category_id": "pack-rice", "slug": "pack-rice-24-servings-cost",
                      "title": "パックご飯24食", "intro": "24食を比較"}

    def test_published_guide_mentions_calculator(self):
        result = category_guide_navigation(self.category, [self.guide])
        self.assertIn("必要な食数から購入箱数", result)
        self.assertIn("../../guides/pack-rice-24-servings-cost/", result)

    def test_unpublished_guide_has_no_link_or_claim(self):
        result = category_guide_navigation(self.category, [])
        self.assertEqual(result, "")

    def test_other_category_does_not_claim_pack_rice_planner(self):
        result = category_guide_navigation(
            {"id": "rice", "name": "お米"},
            [{"category_id": "rice", "slug": "rice-musenmai-cost", "title": "無洗米", "intro": "比較"}],
        )
        self.assertNotIn("必要な食数から購入箱数", result)


if __name__ == "__main__":
    unittest.main()
