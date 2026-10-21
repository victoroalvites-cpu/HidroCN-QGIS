import configparser
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class PackageLayoutTests(unittest.TestCase):
    def test_required_qgis_plugin_files_exist(self):
        for name in (
            "__init__.py", "metadata.txt", "plugin.py", "dialog.py", "icon.png",
            "ui_theme.py", "raster_blocks.py",
        ):
            with self.subTest(name=name):
                self.assertTrue((PLUGIN_ROOT / name).is_file())

    def test_metadata_declares_version_and_qgis_range(self):
        parser = configparser.ConfigParser()
        parser.read(PLUGIN_ROOT / "metadata.txt", encoding="utf-8")
        general = parser["general"]
        self.assertEqual(general["version"], "0.5.3")
        self.assertEqual(general["qgisMinimumVersion"], "3.28")
        self.assertEqual(general["qgisMaximumVersion"], "3.99")
        self.assertEqual(general["experimental"], "False")
        self.assertEqual(
            general["repository"],
            "https://github.com/victoroalvites-cpu/HidroCN-QGIS",
        )
        self.assertTrue(general["tracker"].endswith("/issues"))

    def test_javascript_markdown_escapes_are_not_in_asset_ids(self):
        service = (PLUGIN_ROOT / "gee_service.py").read_text(encoding="utf-8")
        self.assertNotIn("CN\\_Peru", service)
        self.assertIn("CN_Peru", service)


if __name__ == "__main__":
    unittest.main()
