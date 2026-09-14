import csv
import tempfile
import unittest
from pathlib import Path

from hidro_cn_qgis.core.local_cn import read_lookup_csv, write_lookup_template
from hidro_cn_qgis.core.cn_catalog import CATALOGS, write_catalog_lookup


class LookupTests(unittest.TestCase):
    def test_reads_hec_geohms_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lookup.csv"
            path.write_text(
                "LUValue,Description,A,B,C,D\n10,Bosque,30,55,70,77\n",
                encoding="utf-8",
            )
            rows, lookup = read_lookup_csv(path)
            self.assertEqual(rows[0]["lu_value"], 10)
            self.assertEqual(lookup[(10, 1)], 30.0)
            self.assertEqual(lookup[(10, 4)], 77.0)

    def test_reads_scs_cn_builder_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lookup.csv"
            path.write_text(
                "LULC_code,CN_A,CN_B,CN_C,CN_D\n7,100,100,100,100\n",
                encoding="utf-8",
            )
            _, lookup = read_lookup_csv(path)
            self.assertEqual(lookup[(7, 3)], 100.0)

    def test_rejects_missing_columns_and_invalid_cn(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lookup.csv"
            path.write_text("LUValue,A,B,C\n1,20,30,40\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_lookup_csv(path)
            path.write_text("LUValue,A,B,C,D\n1,20,30,40,101\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_lookup_csv(path)

    def test_accepts_blank_group_when_source_does_not_publish_value(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lookup.csv"
            path.write_text(
                "LUValue,Description,A,B,C,D\n8,Matorral arido,,77,85,88\n",
                encoding="utf-8",
            )
            rows, lookup = read_lookup_csv(path)
            self.assertIsNone(rows[0]["A"])
            self.assertNotIn((8, 1), lookup)
            self.assertEqual(lookup[(8, 4)], 88.0)

    def test_writes_empty_hec_geohms_template(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "template.csv"
            write_lookup_template(path)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(next(csv.reader(stream)), ["LUValue", "Description", "A", "B", "C", "D"])

    def test_catalog_writes_traceable_compatible_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.csv"
            write_catalog_lookup(
                path,
                "ana_scs_general",
                [{"lu_value": 10, "description": "Clase local", "entry_key": "ana_rainforest"}],
            )
            rows, lookup = read_lookup_csv(path)
            self.assertEqual(rows[0]["description"], "Clase local")
            self.assertEqual(lookup[(10, 2)], 55.0)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                source_row = next(csv.DictReader(stream))
            self.assertEqual(source_row["CatalogID"], "ana_scs_general")
            self.assertTrue(source_row["SourceURL"].startswith("https://"))

    def test_catalogs_include_general_and_arid_numcurv_flows(self):
        self.assertIn("ana_scs_general", CATALOGS)
        self.assertIn("numcurv_general", CATALOGS)
        self.assertIn("numcurv_arid", CATALOGS)
        self.assertEqual(len(CATALOGS["ana_scs_general"].entries), 13)
        self.assertEqual(len(CATALOGS["numcurv_general"].entries), 57)
        self.assertEqual(len(CATALOGS["numcurv_arid"].entries), 15)
        self.assertTrue(all("(CN-II)" not in catalog.label for catalog in CATALOGS.values()))

    def test_catalog_sentinel_values_match_supplied_tables(self):
        catalogs = {
            key: {entry.key: entry.values for entry in catalog.entries}
            for key, catalog in CATALOGS.items()
        }
        self.assertEqual(
            catalogs["ana_scs_general"]["ana_water"],
            {"A": 100, "B": 100, "C": 100, "D": 100},
        )
        self.assertEqual(
            catalogs["ana_scs_general"]["ana_crops"],
            {"A": 62, "B": 71, "C": 78, "D": 81},
        )
        self.assertEqual(
            catalogs["numcurv_general"]["num_forest_very_good"],
            {"A": 15, "B": 44, "C": 54, "D": 61},
        )
        self.assertEqual(
            catalogs["numcurv_general"]["num_firm_roads"],
            {"A": 74, "B": 84, "C": 90, "D": 92},
        )
        self.assertEqual(
            catalogs["numcurv_arid"]["arid_herb_poor"],
            {"A": 70, "B": 80, "C": 87, "D": 93},
        )


class ArrayTests(unittest.TestCase):
    def test_maps_conditions_and_reports_unmatched(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy no disponible")
        from hidro_cn_qgis.core.local_cn import build_cn_arrays

        lulc = np.array([[1, 1, 2], [2, 9, 1]], dtype=np.float32)
        hsg = np.array([[1, 4, 2], [3, 1, 5]], dtype=np.float32)
        lookup = {(1, 1): 50.0, (1, 4): 80.0, (2, 2): 70.0, (2, 3): 85.0}
        arrays, qc = build_cn_arrays(lulc, hsg, lookup)
        self.assertEqual(float(arrays["II"][0, 0]), 50.0)
        self.assertEqual(float(arrays["II"][1, 0]), 85.0)
        self.assertEqual(float(arrays["II"][1, 1]), -9999.0)
        self.assertEqual(qc["matched_pixels"], 4)
        self.assertEqual(qc["unmatched_pixels"], 2)
        self.assertEqual(qc["unknown_lulc_values"], [1, 9])
        self.assertEqual(qc["unexpected_hsg_values"], [5])
        self.assertLess(float(arrays["I"][0, 0]), 50.0)
        self.assertGreater(float(arrays["III"][0, 0]), 50.0)


if __name__ == "__main__":
    unittest.main()
