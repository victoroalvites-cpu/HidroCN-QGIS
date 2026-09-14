"""Normaliza una copia de un GeoTIFF con una cuenca real para QA manual."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from osgeo import ogr, osr

from hidro_cn_qgis.gee_service import normalize_geotiff_nodata


def basin_geojson(vector_path):
    dataset = ogr.Open(str(vector_path))
    if dataset is None:
        raise RuntimeError("No se pudo abrir la cuenca de prueba.")
    layer = dataset.GetLayer(0)
    source_srs = layer.GetSpatialRef()
    geometry = None
    for feature in layer:
        current = feature.GetGeometryRef()
        if current is None or current.IsEmpty():
            continue
        geometry = current.Clone() if geometry is None else geometry.Union(current)
    if geometry is None:
        raise RuntimeError("La cuenca de prueba no contiene geometria.")
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(4326)
    if hasattr(target_srs, "SetAxisMappingStrategy"):
        target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geometry.Transform(osr.CoordinateTransformation(source_srs, target_srs))
    return json.loads(geometry.ExportToJson())


def main():
    raster_path = sys.argv[1]
    vector_path = sys.argv[2]
    print(normalize_geotiff_nodata(raster_path, basin_geojson(vector_path)))


if __name__ == "__main__":
    main()
