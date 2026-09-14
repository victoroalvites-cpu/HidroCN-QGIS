import math
import unittest

from hidro_cn_qgis.core.cn_conditions import (
    cn_dry_from_normal,
    cn_wet_from_normal,
    derive_cn_conditions,
    validate_cn,
)


class CurveNumberConditionTests(unittest.TestCase):
    def test_known_conversion_for_cn_75(self):
        self.assertAlmostEqual(cn_dry_from_normal(75), 55.752, places=3)
        self.assertAlmostEqual(cn_wet_from_normal(75), 87.342, places=3)

    def test_conditions_are_ordered(self):
        for normal in (30, 55, 75, 95, 100):
            values = derive_cn_conditions(normal)
            self.assertLessEqual(values["I"], values["II"])
            self.assertLessEqual(values["II"], values["III"])
            self.assertGreater(values["I"], 0)
            self.assertLessEqual(values["III"], 100)

    def test_cn_100_remains_100_for_all_conditions(self):
        values = derive_cn_conditions(100)
        for value in values.values():
            self.assertAlmostEqual(value, 100.0, places=10)

    def test_invalid_values_are_rejected(self):
        for value in (None, "", 0, -1, 100.1, math.inf, math.nan):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_cn(value)


if __name__ == "__main__":
    unittest.main()
