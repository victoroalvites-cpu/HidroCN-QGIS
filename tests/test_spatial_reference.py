import unittest

from hidro_cn_qgis.core.spatial_reference import suggested_utm_authid, utm_zone


class SpatialReferenceTests(unittest.TestCase):
    def test_peru_longitudes_map_to_expected_zones(self):
        self.assertEqual(utm_zone(-79.0), 17)
        self.assertEqual(utm_zone(-75.0), 18)
        self.assertEqual(utm_zone(-70.0), 19)

    def test_southern_hemisphere_uses_epsg_327xx(self):
        self.assertEqual(suggested_utm_authid(-75.0, -10.0), "EPSG:32718")

    def test_northern_hemisphere_uses_epsg_326xx(self):
        self.assertEqual(suggested_utm_authid(-75.0, 10.0), "EPSG:32618")

    def test_invalid_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            utm_zone(181)
        with self.assertRaises(ValueError):
            suggested_utm_authid(-75, -81)


if __name__ == "__main__":
    unittest.main()
