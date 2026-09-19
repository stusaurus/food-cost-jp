import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from build_site import parse_quantity, unit_prices

class UnitTests(unittest.TestCase):
    def test_pack_rice(self):
        q = parse_quantity("パックご飯 200g×24食 送料無料", "pack-rice")
        self.assertEqual(q["count"], 24)
        self.assertAlmostEqual(unit_prices(3980, q, "pack-rice")["per_serving"], 3980 / 24)

    def test_rice(self):
        q = parse_quantity("国産米 5kg×2袋 送料無料", "rice")
        self.assertEqual(q["total_weight_g"], 10000)
        self.assertAlmostEqual(unit_prices(4980, q, "rice")["per_kg"], 498)

    def test_water(self):
        q = parse_quantity("強炭酸水 500ml×48本 送料無料", "carbonated-water")
        self.assertEqual(q["total_volume_ml"], 24000)
        self.assertEqual(unit_prices(2880, q, "carbonated-water")["per_bottle"], 60)

    def test_selectable_rejected(self):
        self.assertIsNone(parse_quantity("白米 選べる 5kg 10kg", "rice"))

if __name__ == "__main__":
    unittest.main()
