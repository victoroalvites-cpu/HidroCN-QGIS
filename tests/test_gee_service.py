import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from hidro_cn_qgis.gee_service import (
    CN_PERU_ASSET,
    GCN250_AVERAGE_ASSET,
    GCN250_DRY_ASSET,
    GCN250_WET_ASSET,
    SOURCE_CATALOG,
    _available_path,
    _safe_prefix,
    _source,
    _validated_gee_download_url,
    _validated_conditions,
    initialize_ee,
)
from hidro_cn_qgis.gee_worker_helper import execute


class GeeServiceOfflineTests(unittest.TestCase):
    def test_catalog_contains_the_agreed_assets(self):
        self.assertEqual(SOURCE_CATALOG["cn_peru"].assets["II"], CN_PERU_ASSET)
        self.assertEqual(SOURCE_CATALOG["gcn250"].assets["I"], GCN250_DRY_ASSET)
        self.assertEqual(SOURCE_CATALOG["gcn250"].assets["II"], GCN250_AVERAGE_ASSET)
        self.assertEqual(SOURCE_CATALOG["gcn250"].assets["III"], GCN250_WET_ASSET)

    def test_custom_asset_is_interpreted_as_normal_condition(self):
        definition = _source("custom", "projects/example/assets/cn", "curve_number")
        self.assertEqual(definition.assets, {"II": "projects/example/assets/cn"})
        self.assertEqual(definition.default_band, "curve_number")

    def test_conditions_are_deduplicated_and_hydrologically_ordered(self):
        self.assertEqual(_validated_conditions(["III", "I", "II", "I"]), ["I", "II", "III"])

    def test_prefix_is_safe_for_output_files(self):
        self.assertEqual(_safe_prefix("Cuenca Tucuhuayin / 2026"), "Cuenca_Tucuhuayin_2026")

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "cuenca_CN_II_normal.tif"
            target.touch()
            self.assertEqual(
                _available_path(target).name,
                "cuenca_CN_II_normal_2.tif",
            )

    def test_download_url_requires_https_google_host(self):
        valid = "https://earthengine.googleapis.com/v1/projects/example/image:download"
        self.assertEqual(_validated_gee_download_url(valid), valid)
        for invalid in (
            "http://earthengine.googleapis.com/download",
            "file:///C:/Windows/win.ini",
            "https://example.com/raster.tif",
            "",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(Exception):
                _validated_gee_download_url(invalid)

    def test_initialize_sets_deadline_after_session(self):
        calls = []

        class FakeData:
            @staticmethod
            def setDeadline(value):
                calls.append(("deadline", value))

        class FakeValue:
            @staticmethod
            def getInfo():
                calls.append(("get_info", None))
                return "conexion_correcta"

        class FakeEe:
            __version__ = "test"
            data = FakeData()

            @staticmethod
            def Initialize(project):
                calls.append(("initialize", project))

            @staticmethod
            def String(value):
                return FakeValue()

        with patch("hidro_cn_qgis.gee_service._load_ee", return_value=FakeEe()):
            result = initialize_ee("ee-hidrog")

        self.assertEqual(calls[0], ("initialize", "ee-hidrog"))
        self.assertEqual(calls[1], ("deadline", 60000))
        self.assertEqual(result["test"], "conexion_correcta")

    def test_external_worker_forwards_subbasins_for_areal_statistics(self):
        subbasins = [{"id": "S01", "geometry": {"type": "Polygon", "coordinates": []}}]
        request = {
            "operation": "download",
            "project_id": "ee-hidrog",
            "source_key": "cn_peru",
            "geometry_geojson": {"type": "Polygon", "coordinates": [[[0, 0]]]},
            "conditions": ["II"],
            "output_crs": "EPSG:32718",
            "scale_m": 90,
            "output_folder": "salida",
            "prefix": "cn",
            "features": subbasins,
            "id_field": "SUB_ID",
        }
        with patch(
            "hidro_cn_qgis.gee_worker_helper.initialize_ee",
            return_value={"project": "ee-hidrog"},
        ), patch(
            "hidro_cn_qgis.gee_worker_helper.download_cn_products",
            return_value={"outputs": []},
        ) as download:
            self.assertEqual(execute(request), {"outputs": []})
        self.assertEqual(download.call_args.args[-3], subbasins)
        self.assertEqual(download.call_args.args[-2], "SUB_ID")
        self.assertTrue(callable(download.call_args.args[-1]))


if __name__ == "__main__":
    unittest.main()
