"""Prueba minima de carga dentro del Python real de QGIS.

Se ejecuta manualmente con ``python-qgis-ltr.bat``; no forma parte del
descubrimiento de unittest porque requiere las bibliotecas nativas de QGIS.
"""

import os
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Python 3.8+ ya no usa PATH de la misma manera para dependencias DLL. La
# aplicacion QGIS las tiene cargadas, pero una prueba Python independiente debe
# registrar explicitamente sus carpetas nativas.
_dll_handles = []
if os.name == "nt" and hasattr(os, "add_dll_directory"):
    qgis_prefix = Path(os.environ.get("QGIS_PREFIX_PATH", ""))
    if qgis_prefix.is_dir():
        qgis_root = qgis_prefix.parents[1]
        for folder in (
            qgis_root / "bin",
            qgis_prefix / "bin",
            qgis_root / "apps" / "qt5" / "bin",
            qgis_root / "apps" / "gdal" / "bin",
        ):
            if folder.is_dir():
                _dll_handles.append(os.add_dll_directory(str(folder)))

from qgis.core import QgsApplication, QgsProject


def main():
    app = QgsApplication([], False)
    app.initQgis()
    try:
        import hidro_cn_qgis
        from hidro_cn_qgis.dialog import HidroCnDialog
        from hidro_cn_qgis.cn_table_dialog import CnTableBuilderDialog
        from hidro_cn_qgis.gee_service import dependency_status, normalize_geotiff_nodata
        from hidro_cn_qgis.local_cn_service import (
            run_local_cn_workflow,
            summarize_cn_rasters,
            unique_integer_raster_values,
        )

        assert callable(hidro_cn_qgis.classFactory)
        dialog = HidroCnDialog(None)
        assert dialog.windowTitle() == "HidroCN - Curva Numero"
        assert dialog.source_combo.count() == 3
        assert dialog.method_tabs.count() == 2
        assert dialog.local_catalog_button.text() == "Biblioteca ANA / NumCurv"
        catalog_dialog = CnTableBuilderDialog([1, 2, 10], tempfile.gettempdir())
        assert catalog_dialog.catalog_combo.count() == 3
        assert catalog_dialog.table.rowCount() == 3
        catalog_dialog.close()
        print("HIDROCN_GEE_DEPENDENCY=" + str(dependency_status()))

        import numpy as np
        from osgeo import gdal, osr

        gdal.UseExceptions()

        with tempfile.TemporaryDirectory(prefix="hidrocn_nodata_") as folder:
            raster_path = Path(folder) / "mask_test.tif"
            dataset = gdal.GetDriverByName("GTiff").Create(
                str(raster_path), 4, 2, 1, gdal.GDT_Float32
            )
            dataset.SetGeoTransform((0.0, 1.0, 0.0, 2.0, 0.0, -1.0))
            spatial_reference = osr.SpatialReference()
            spatial_reference.ImportFromEPSG(4326)
            dataset.SetProjection(spatial_reference.ExportToWkt())
            band = dataset.GetRasterBand(1)
            band.WriteArray(
                np.array(
                    [[-np.inf, 0.0, 10.0, 100.0], [np.nan, -1.0, 50.0, 101.0]],
                    dtype=np.float32,
                )
            )
            dataset = None
            right_half = {
                "type": "Polygon",
                "coordinates": [[[2, 0], [4, 0], [4, 2], [2, 2], [2, 0]]],
            }
            result = normalize_geotiff_nodata(str(raster_path), right_half)
            dataset = gdal.Open(str(raster_path))
            band = dataset.GetRasterBand(1)
            values = band.ReadAsArray()
            assert band.GetNoDataValue() == -9999.0
            assert result["replaced_pixels"] == 5
            assert int(np.count_nonzero(values == -9999.0)) == 5
            assert values[0, 2] == 10.0 and values[0, 3] == 100.0
            dataset = None
            dialog._add_cn_raster(
                str(raster_path),
                "II",
                {"minimum": 10.0, "maximum": 100.0},
            )
            loaded = list(QgsProject.instance().mapLayers().values())
            assert len(loaded) == 1
            renderer = loaded[0].renderer()
            assert renderer.classificationMin() == 10.0
            assert renderer.classificationMax() == 100.0
            QgsProject.instance().removeAllMapLayers()
        print("HIDROCN_NODATA_SMOKE=OK")
        print("HIDROCN_DYNAMIC_RAMP_SMOKE=OK")

        with tempfile.TemporaryDirectory(prefix="hidrocn_local_") as folder:
            folder = Path(folder)
            spatial_reference = osr.SpatialReference()
            spatial_reference.ImportFromEPSG(32718)

            def make_raster(path, values):
                dataset = gdal.GetDriverByName("GTiff").Create(
                    str(path), 4, 2, 1, gdal.GDT_Float32
                )
                dataset.SetGeoTransform((0.0, 1.0, 0.0, 2.0, 0.0, -1.0))
                dataset.SetProjection(spatial_reference.ExportToWkt())
                dataset.GetRasterBand(1).SetNoDataValue(-9999.0)
                dataset.GetRasterBand(1).WriteArray(np.array(values, dtype=np.float32))
                dataset = None

            lulc = folder / "lulc.tif"
            hsg = folder / "hsg.tif"
            lookup = folder / "lookup.csv"
            make_raster(lulc, [[1, 1, 2, 2], [1, 9, 2, 2]])
            make_raster(hsg, [[1, 4, 2, 3], [1, 1, 2, 4]])
            assert unique_integer_raster_values(lulc) == [1, 2, 9]
            lookup.write_text(
                "LUValue,Description,A,B,C,D\n"
                "1,Bosque,30,55,70,77\n"
                "2,Cultivo,67,78,85,89\n",
                encoding="utf-8",
            )
            local_result = run_local_cn_workflow(
                {
                    "lulc_path": str(lulc),
                    "hsg_path": str(hsg),
                    "lookup_csv": str(lookup),
                    "features": [
                        {"id": "Oeste", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}},
                        {"id": "Este", "geometry": {"type": "Polygon", "coordinates": [[[2, 0], [4, 0], [4, 2], [2, 2], [2, 0]]]}},
                    ],
                    "id_field": "nombre",
                    "conditions": ["I", "II", "III"],
                    "output_crs": "EPSG:32718",
                    "resolution_m": 1.0,
                    "output_folder": str(folder),
                    "prefix": "prueba",
                }
            )
            assert len(local_result["outputs"]) == 3
            assert local_result["quality_control"]["matched_pixels"] == 7
            assert local_result["quality_control"]["unmatched_pixels"] == 1
            assert local_result["quality_control"]["unknown_lulc_values"] == [9]
            assert Path(local_result["statistics_csv"]).is_file()
            assert Path(local_result["subbasins_gpkg"]).is_file()
            metadata = json.loads(Path(local_result["metadata_path"]).read_text(encoding="utf-8"))
            assert len(metadata["subbasin_statistics"]) == 2
            gee_summary = summarize_cn_rasters(
                [
                    {"id": "Oeste", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}},
                    {"id": "Este", "geometry": {"type": "Polygon", "coordinates": [[[2, 0], [4, 0], [4, 2], [2, 2], [2, 0]]]}},
                ],
                local_result["outputs"],
                "EPSG:32718",
                folder / "gee_CN_por_subcuenca.csv",
                folder / "gee_subcuencas_CN.gpkg",
            )
            assert len(gee_summary["rows"]) == 2
            assert abs(gee_summary["rows"][0]["CN_II_MEAN"] - (137.0 / 3.0)) < 1e-6
            assert gee_summary["rows"][0]["CN_II_COV"] == 75.0
            assert gee_summary["rows"][1]["CN_II_COV"] == 100.0
            assert Path(gee_summary["statistics_csv"]).is_file()
            assert Path(gee_summary["subbasins_gpkg"]).is_file()
        print("HIDROCN_LOCAL_HEC_GEOHMS_SMOKE=OK")
        print("HIDROCN_GEE_ZONAL_SMOKE=OK")
        dialog.close()
        print("HIDROCN_QGIS_SMOKE=OK")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
