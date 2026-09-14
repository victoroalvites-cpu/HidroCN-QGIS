"""Flujo local de numero de curva sobre una malla comun proyectada."""

from __future__ import annotations

import csv
import html
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core.local_cn import build_cn_arrays, read_lookup_csv


NODATA = -9999.0
CONDITION_SUFFIX = {"I": "CN_I_seca", "II": "CN_II_normal", "III": "CN_III_humeda"}


class LocalCnError(RuntimeError):
    """Error explicable al usuario durante el procesamiento local."""


def _imports():
    try:
        import numpy as np
        from osgeo import gdal, ogr, osr
    except Exception as error:
        raise LocalCnError(
            "El calculo local necesita NumPy y GDAL/OGR incluidos con QGIS. "
            f"No fue posible cargarlos: {error}"
        ) from error
    gdal.UseExceptions()
    return np, gdal, ogr, osr


def unique_integer_raster_values(path, max_values=512):
    """Devuelve los codigos enteros de la primera banda sin cargar todo el raster."""

    np, gdal, _ogr, _osr = _imports()
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None or dataset.RasterCount < 1:
        raise LocalCnError(f"No fue posible abrir el raster de uso del suelo: {path}")
    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    block_x, block_y = band.GetBlockSize()
    block_x = max(1, block_x or 256)
    block_y = max(1, block_y or 256)
    values = set()
    for y_offset in range(0, dataset.RasterYSize, block_y):
        height = min(block_y, dataset.RasterYSize - y_offset)
        for x_offset in range(0, dataset.RasterXSize, block_x):
            width = min(block_x, dataset.RasterXSize - x_offset)
            array = band.ReadAsArray(x_offset, y_offset, width, height)
            if array is None:
                continue
            valid = np.isfinite(array)
            if nodata is not None:
                valid &= ~np.isclose(array, nodata, atol=1e-6)
            sample = array[valid]
            if not sample.size:
                continue
            if not np.all(np.isclose(sample, np.rint(sample), atol=1e-6)):
                raise LocalCnError(
                    "El raster de uso del suelo contiene valores decimales. "
                    "Reclasifiquelo a codigos enteros antes de crear la tabla CN."
                )
            values.update(int(value) for value in np.unique(np.rint(sample)))
            if len(values) > int(max_values):
                raise LocalCnError(
                    f"El raster contiene mas de {max_values} clases. "
                    "Revise que sea un raster categorico de uso del suelo."
                )
    dataset = None
    if not values:
        raise LocalCnError("El raster de uso del suelo no contiene clases validas.")
    return sorted(values)


def _safe_stem(folder, prefix):
    clean = "".join(char if char.isalnum() or char in "_-" else "_" for char in prefix.strip())
    clean = clean.strip("_") or "hidrocn"
    candidate = clean
    index = 2
    while any(Path(folder).glob(candidate + "_*")):
        candidate = f"{clean}_{index}"
        index += 1
    return candidate


def _spatial_reference(authid, osr):
    try:
        epsg = int(str(authid).split(":", 1)[1])
    except (IndexError, ValueError) as error:
        raise LocalCnError(f"SRC proyectado no compatible: {authid!r}.") from error
    spatial_reference = osr.SpatialReference()
    if spatial_reference.ImportFromEPSG(epsg) != 0:
        raise LocalCnError(f"GDAL no pudo crear el SRC {authid}.")
    if hasattr(spatial_reference, "SetAxisMappingStrategy"):
        spatial_reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return spatial_reference


def _geometry_from_geojson(value, ogr):
    geometry = ogr.CreateGeometryFromJson(json.dumps(value))
    if geometry is None or geometry.IsEmpty():
        raise LocalCnError("Una geometria de subcuenca es vacia o no es valida.")
    return geometry


def _aligned_bounds(features, resolution, ogr):
    envelopes = [_geometry_from_geojson(item["geometry"], ogr).GetEnvelope() for item in features]
    min_x = min(item[0] for item in envelopes)
    max_x = max(item[1] for item in envelopes)
    min_y = min(item[2] for item in envelopes)
    max_y = max(item[3] for item in envelopes)
    left = math.floor(min_x / resolution) * resolution
    right = math.ceil(max_x / resolution) * resolution
    bottom = math.floor(min_y / resolution) * resolution
    top = math.ceil(max_y / resolution) * resolution
    columns = max(1, int(round((right - left) / resolution)))
    rows = max(1, int(round((top - bottom) / resolution)))
    return (left, bottom, right, top), columns, rows


def _warp_input(source, destination, authid, bounds, columns, rows, gdal):
    try:
        dataset = gdal.Open(str(source), gdal.GA_ReadOnly)
    except Exception as error:
        raise LocalCnError(f"No fue posible abrir el raster {source}: {error}") from error
    if dataset is None or dataset.RasterCount < 1:
        raise LocalCnError(f"Raster invalido o sin bandas: {source}")
    source_nodata = dataset.GetRasterBand(1).GetNoDataValue()
    dataset = None
    options = gdal.WarpOptions(
        format="GTiff",
        dstSRS=authid,
        outputBounds=bounds,
        width=columns,
        height=rows,
        resampleAlg=gdal.GRA_NearestNeighbour,
        srcNodata=source_nodata,
        dstNodata=NODATA,
        outputType=gdal.GDT_Float32,
        multithread=True,
        creationOptions=["TILED=YES", "COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"],
    )
    result = gdal.Warp(str(destination), str(source), options=options)
    if result is None:
        raise LocalCnError(f"GDAL no pudo alinear {source}.")
    result.GetRasterBand(1).SetNoDataValue(NODATA)
    result = None


def _memory_vector(features, spatial_reference, ogr):
    memory_driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
    datasource = memory_driver.CreateDataSource("")
    layer = datasource.CreateLayer("subcuencas", spatial_reference, geom_type=ogr.wkbUnknown)
    layer.CreateField(ogr.FieldDefn("ZONE_ID", ogr.OFTInteger))
    definition = layer.GetLayerDefn()
    for zone_id, item in enumerate(features, start=1):
        feature = ogr.Feature(definition)
        feature.SetField("ZONE_ID", zone_id)
        feature.SetGeometry(_geometry_from_geojson(item["geometry"], ogr))
        if layer.CreateFeature(feature) != 0:
            raise LocalCnError(f"No fue posible preparar la subcuenca {item['id']}.")
        feature = None
    return datasource, layer


def _create_zone_raster(path, features, spatial_reference, bounds, columns, rows, resolution, gdal, ogr):
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), columns, rows, 1, gdal.GDT_Int32,
        options=["TILED=YES", "COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"],
    )
    dataset.SetGeoTransform((bounds[0], resolution, 0.0, bounds[3], 0.0, -resolution))
    dataset.SetProjection(spatial_reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(0)
    band.Fill(0)
    datasource, layer = _memory_vector(features, spatial_reference, ogr)
    result = gdal.RasterizeLayer(dataset, [1], layer, options=["ATTRIBUTE=ZONE_ID"])
    datasource = None
    dataset = None
    if result != 0:
        raise LocalCnError("No fue posible rasterizar las subcuencas sobre la malla de calculo.")


def _create_output_raster(path, reference, gdal):
    source = gdal.Open(str(reference), gdal.GA_ReadOnly)
    output = gdal.GetDriverByName("GTiff").Create(
        str(path), source.RasterXSize, source.RasterYSize, 1, gdal.GDT_Float32,
        options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"],
    )
    output.SetGeoTransform(source.GetGeoTransform())
    output.SetProjection(source.GetProjection())
    output.GetRasterBand(1).SetNoDataValue(NODATA)
    source = None
    return output


def _process_rasters(lulc_path, hsg_path, zone_path, output_paths, lookup, gdal, np):
    lulc_ds = gdal.Open(str(lulc_path), gdal.GA_ReadOnly)
    hsg_ds = gdal.Open(str(hsg_path), gdal.GA_ReadOnly)
    zone_ds = gdal.Open(str(zone_path), gdal.GA_ReadOnly)
    outputs = {condition: _create_output_raster(path, lulc_path, gdal) for condition, path in output_paths.items()}
    block_x, block_y = lulc_ds.GetRasterBand(1).GetBlockSize()
    block_x = max(1, block_x)
    block_y = max(1, block_y)
    qc = {
        "valid_input_pixels": 0,
        "matched_pixels": 0,
        "unmatched_pixels": 0,
        "outside_or_nodata_pixels": 0,
        "unknown_lulc_values": set(),
        "unknown_hsg_values": set(),
        "unexpected_hsg_values": set(),
    }
    zonal = {condition: {} for condition in output_paths}
    zone_totals = {}

    for y_offset in range(0, lulc_ds.RasterYSize, block_y):
        height = min(block_y, lulc_ds.RasterYSize - y_offset)
        for x_offset in range(0, lulc_ds.RasterXSize, block_x):
            width = min(block_x, lulc_ds.RasterXSize - x_offset)
            lulc = lulc_ds.GetRasterBand(1).ReadAsArray(x_offset, y_offset, width, height)
            hsg = hsg_ds.GetRasterBand(1).ReadAsArray(x_offset, y_offset, width, height)
            zones = zone_ds.GetRasterBand(1).ReadAsArray(x_offset, y_offset, width, height)
            basin_mask = zones > 0
            arrays, block_qc = build_cn_arrays(lulc, hsg, lookup, NODATA, basin_mask)
            for key in ("valid_input_pixels", "matched_pixels", "unmatched_pixels", "outside_or_nodata_pixels"):
                qc[key] += block_qc[key]
            for key in ("unknown_lulc_values", "unknown_hsg_values", "unexpected_hsg_values"):
                qc[key].update(block_qc[key])
            for zone_id in np.unique(zones[basin_mask]):
                zone_id = int(zone_id)
                zone_mask = zones == zone_id
                zone_totals[zone_id] = zone_totals.get(zone_id, 0) + int(np.count_nonzero(zone_mask))
                for condition, array in arrays.items():
                    if condition not in outputs:
                        continue
                    valid = zone_mask & (array != NODATA) & np.isfinite(array)
                    values = array[valid]
                    if values.size:
                        item = zonal[condition].setdefault(
                            zone_id, {"count": 0, "sum": 0.0, "minimum": math.inf, "maximum": -math.inf}
                        )
                        item["count"] += int(values.size)
                        item["sum"] += float(values.sum(dtype=np.float64))
                        item["minimum"] = min(item["minimum"], float(values.min()))
                        item["maximum"] = max(item["maximum"], float(values.max()))
            for condition, output in outputs.items():
                output.GetRasterBand(1).WriteArray(arrays[condition], x_offset, y_offset)

    if not qc["matched_pixels"]:
        for dataset in outputs.values():
            dataset = None
        outputs.clear()
        lulc_ds = hsg_ds = zone_ds = None
        for path in output_paths.values():
            try:
                Path(path).unlink()
            except OSError:
                pass
        raise LocalCnError(
            "Ninguna celda pudo relacionarse con la tabla CN. "
            f"Codigos LULC observados sin correspondencia: {sorted(qc['unknown_lulc_values'])}; "
            f"valores HSG observados: {sorted(qc['unknown_hsg_values'])}."
        )

    result_stats = {}
    for condition, output in outputs.items():
        band = output.GetRasterBand(1)
        statistics = band.ComputeStatistics(False)
        result_stats[condition] = {
            "minimum": statistics[0], "maximum": statistics[1],
            "mean": statistics[2], "stddev": statistics[3],
        }
        output = None
    outputs.clear()
    lulc_ds = hsg_ds = zone_ds = None
    for key in ("unknown_lulc_values", "unknown_hsg_values", "unexpected_hsg_values"):
        qc[key] = sorted(qc[key])
    qc["match_pct"] = (
        100.0 * qc["matched_pixels"] / qc["valid_input_pixels"]
        if qc["valid_input_pixels"] else 0.0
    )
    return qc, zonal, zone_totals, result_stats


def _zonal_rows(features, conditions, zonal, zone_totals):
    rows = []
    for zone_id, feature in enumerate(features, start=1):
        row = {"SUB_ID": str(feature["id"]), "PIXELS": zone_totals.get(zone_id, 0)}
        for condition in conditions:
            values = zonal.get(condition, {}).get(zone_id)
            prefix = f"CN_{condition}"
            if not values or not values["count"]:
                row.update({f"{prefix}_MEAN": None, f"{prefix}_MIN": None, f"{prefix}_MAX": None, f"{prefix}_COV": 0.0})
            else:
                row.update({
                    f"{prefix}_MEAN": values["sum"] / values["count"],
                    f"{prefix}_MIN": values["minimum"],
                    f"{prefix}_MAX": values["maximum"],
                    f"{prefix}_COV": 100.0 * values["count"] / max(1, row["PIXELS"]),
                })
        rows.append(row)
    return rows


def _write_csv(path, rows):
    fields = list(rows[0]) if rows else ["SUB_ID"]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_geopackage(path, features, rows, spatial_reference, ogr):
    driver = ogr.GetDriverByName("GPKG")
    datasource = driver.CreateDataSource(str(path))
    if datasource is None:
        raise LocalCnError(f"No fue posible crear {path}.")
    layer = datasource.CreateLayer("subcuencas_cn", spatial_reference, geom_type=ogr.wkbUnknown)
    for field_name in rows[0].keys():
        field_type = ogr.OFTString if field_name == "SUB_ID" else (ogr.OFTInteger64 if field_name == "PIXELS" else ogr.OFTReal)
        layer.CreateField(ogr.FieldDefn(field_name, field_type))
    definition = layer.GetLayerDefn()
    for item, values in zip(features, rows):
        feature = ogr.Feature(definition)
        for field_name, value in values.items():
            if value is not None:
                feature.SetField(field_name, value)
        feature.SetGeometry(_geometry_from_geojson(item["geometry"], ogr))
        if layer.CreateFeature(feature) != 0:
            raise LocalCnError(f"No fue posible escribir la subcuenca {item['id']}.")
        feature = None
    datasource = None


def summarize_cn_rasters(features, outputs, output_crs, csv_path, gpkg_path):
    """Calcula estadisticas zonales de raster CN ya generados.

    Las geometrías deben estar expresadas en ``output_crs``. Se usa la malla
    exacta del primer GeoTIFF para que PIXELS y cobertura sean comparables con
    los valores descargados, incluidos sus NoData.
    """

    np, gdal, ogr, osr = _imports()
    features = list(features or [])
    output_items = [item for item in (outputs or []) if item.get("condition") and item.get("path")]
    if not features:
        raise LocalCnError("No se recibieron subunidades para calcular estadisticas areales.")
    if not output_items:
        raise LocalCnError("No se recibieron raster CN para calcular estadisticas areales.")

    reference = gdal.Open(str(output_items[0]["path"]), gdal.GA_ReadOnly)
    if reference is None or reference.RasterCount < 1:
        raise LocalCnError(f"No fue posible abrir {output_items[0]['path']} para el resumen areal.")
    columns = reference.RasterXSize
    rows_count = reference.RasterYSize
    geotransform = reference.GetGeoTransform()
    projection = reference.GetProjection()
    block_x, block_y = reference.GetRasterBand(1).GetBlockSize()
    block_x = max(1, block_x or 256)
    block_y = max(1, block_y or 256)
    reference = None

    spatial_reference = _spatial_reference(output_crs, osr)
    conditions = [item["condition"] for item in output_items]
    zonal = {condition: {} for condition in conditions}
    zone_totals = {}

    with tempfile.TemporaryDirectory(prefix="hidrocn_gee_zonal_") as folder:
        zone_path = Path(folder) / "subunidades.tif"
        zone_dataset = gdal.GetDriverByName("GTiff").Create(
            str(zone_path), columns, rows_count, 1, gdal.GDT_Int32,
            options=["TILED=YES", "COMPRESS=DEFLATE"],
        )
        if zone_dataset is None:
            raise LocalCnError("No fue posible crear la malla temporal de subunidades.")
        zone_dataset.SetGeoTransform(geotransform)
        zone_dataset.SetProjection(projection)
        zone_band = zone_dataset.GetRasterBand(1)
        zone_band.SetNoDataValue(0)
        zone_band.Fill(0)
        datasource, layer = _memory_vector(features, spatial_reference, ogr)
        if gdal.RasterizeLayer(zone_dataset, [1], layer, options=["ATTRIBUTE=ZONE_ID"]) != 0:
            raise LocalCnError("No fue posible rasterizar las subunidades sobre la descarga GEE.")
        datasource = None
        zone_dataset = None

        zone_dataset = gdal.Open(str(zone_path), gdal.GA_ReadOnly)
        for y_offset in range(0, rows_count, block_y):
            height = min(block_y, rows_count - y_offset)
            for x_offset in range(0, columns, block_x):
                width = min(block_x, columns - x_offset)
                zones = zone_dataset.GetRasterBand(1).ReadAsArray(
                    x_offset, y_offset, width, height
                )
                for zone_id in np.unique(zones[zones > 0]):
                    integer_id = int(zone_id)
                    zone_totals[integer_id] = zone_totals.get(integer_id, 0) + int(
                        np.count_nonzero(zones == integer_id)
                    )

        for item in output_items:
            condition = item["condition"]
            dataset = gdal.Open(str(item["path"]), gdal.GA_ReadOnly)
            if dataset is None or dataset.RasterCount < 1:
                raise LocalCnError(f"No fue posible abrir {item['path']} para el resumen areal.")
            if dataset.RasterXSize != columns or dataset.RasterYSize != rows_count:
                raise LocalCnError("Los raster CN descargados no comparten las mismas dimensiones.")
            if not np.allclose(dataset.GetGeoTransform(), geotransform, rtol=0.0, atol=1e-8):
                raise LocalCnError("Los raster CN descargados no comparten la misma malla.")
            band = dataset.GetRasterBand(1)
            nodata = band.GetNoDataValue()
            for y_offset in range(0, rows_count, block_y):
                height = min(block_y, rows_count - y_offset)
                for x_offset in range(0, columns, block_x):
                    width = min(block_x, columns - x_offset)
                    zones = zone_dataset.GetRasterBand(1).ReadAsArray(
                        x_offset, y_offset, width, height
                    )
                    values = band.ReadAsArray(x_offset, y_offset, width, height)
                    valid = (zones > 0) & np.isfinite(values) & (values > 0) & (values <= 100)
                    if nodata is not None:
                        valid &= ~np.isclose(values, nodata, atol=1e-6)
                    for zone_id in np.unique(zones[valid]):
                        integer_id = int(zone_id)
                        sample = values[valid & (zones == integer_id)]
                        accumulator = zonal[condition].setdefault(
                            integer_id,
                            {"count": 0, "sum": 0.0, "minimum": math.inf, "maximum": -math.inf},
                        )
                        accumulator["count"] += int(sample.size)
                        accumulator["sum"] += float(sample.sum(dtype=np.float64))
                        accumulator["minimum"] = min(
                            accumulator["minimum"], float(sample.min())
                        )
                        accumulator["maximum"] = max(
                            accumulator["maximum"], float(sample.max())
                        )
            dataset = None
        zone_dataset = None

    zonal_rows = _zonal_rows(features, conditions, zonal, zone_totals)
    _write_csv(csv_path, zonal_rows)
    _write_geopackage(gpkg_path, features, zonal_rows, spatial_reference, ogr)
    return {
        "rows": zonal_rows,
        "statistics_csv": str(csv_path),
        "subbasins_gpkg": str(gpkg_path),
    }


def _write_report(path, metadata):
    rows = metadata["subbasin_statistics"]
    fields = list(rows[0]) if rows else []
    table_header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    table_rows = "".join(
        "<tr>" + "".join(
            f"<td>{html.escape('' if row[field] is None else (f'{row[field]:.3f}' if isinstance(row[field], float) else str(row[field])))}</td>"
            for field in fields
        ) + "</tr>" for row in rows
    )
    qc = metadata["quality_control"]
    warning = "" if not qc["unmatched_pixels"] else (
        f"<p class='warn'>Atencion: {qc['unmatched_pixels']} pixeles validos no tuvieron correspondencia y quedaron como NoData.</p>"
    )
    content = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Informe HidroCN local</title><style>body{{font-family:Arial,sans-serif;margin:32px;color:#222}}
h1,h2{{color:#1f4e5f}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #bbb;padding:6px}}
th{{background:#eef4f6}}.warn{{color:#a14d00;font-weight:bold}}</style></head><body>
<h1>HidroCN - Metodo local HEC-GeoHMS</h1>
<p>Generado: {html.escape(metadata['created_utc'])}</p>
<p>CN-II se asigna mediante el cruce del codigo de uso del suelo con el grupo hidrologico A-D. CN-I y CN-III se derivan con las relaciones (1) y (2) de ANA (2015).</p>
<h2>Control de calidad</h2>{warning}<ul>
<li>Pixeles emparejados: {qc['matched_pixels']} ({qc['match_pct']:.2f} % de las entradas validas)</li>
<li>Clases LULC no encontradas: {html.escape(str(qc['unknown_lulc_values']))}</li>
<li>Valores HSG inesperados: {html.escape(str(qc['unexpected_hsg_values']))}</li></ul>
<h2>Promedio espacial por subcuenca</h2><table><thead><tr>{table_header}</tr></thead><tbody>{table_rows}</tbody></table>
</body></html>"""
    Path(path).write_text(content, encoding="utf-8")


def run_local_cn_workflow(payload):
    """Ejecuta el flujo local con datos serializables, apto para ``QgsTask``."""

    np, gdal, ogr, osr = _imports()
    features = payload.get("features") or []
    if not features:
        raise LocalCnError("No se recibieron subcuencas para el calculo local.")
    conditions = [condition for condition in payload.get("conditions", []) if condition in CONDITION_SUFFIX]
    if not conditions:
        raise LocalCnError("Seleccione al menos una condicion antecedente.")
    resolution = float(payload.get("resolution_m", 0))
    if not math.isfinite(resolution) or resolution <= 0:
        raise LocalCnError("La resolucion debe ser mayor que cero.")
    rows_lookup, lookup = read_lookup_csv(payload["lookup_csv"])
    output_folder = Path(payload["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(output_folder, payload.get("prefix", "hidrocn") + "_local")
    spatial_reference = _spatial_reference(payload["output_crs"], osr)
    bounds, columns, rows = _aligned_bounds(features, resolution, ogr)
    if columns * rows > 1_000_000_000:
        raise LocalCnError(
            f"La malla tendria {columns:,} x {rows:,} celdas. Aumente la resolucion o revise la cuenca."
        )

    lulc_aligned = output_folder / f"{stem}_LULC_alineado.tif"
    hsg_aligned = output_folder / f"{stem}_HSG_alineado.tif"
    zones_path = output_folder / f"{stem}_zonas.tif"
    _warp_input(payload["lulc_path"], lulc_aligned, payload["output_crs"], bounds, columns, rows, gdal)
    _warp_input(payload["hsg_path"], hsg_aligned, payload["output_crs"], bounds, columns, rows, gdal)
    _create_zone_raster(zones_path, features, spatial_reference, bounds, columns, rows, resolution, gdal, ogr)

    output_paths = {
        condition: output_folder / f"{stem}_{CONDITION_SUFFIX[condition]}.tif"
        for condition in conditions
    }
    qc, zonal, zone_totals, global_stats = _process_rasters(
        lulc_aligned, hsg_aligned, zones_path, output_paths, lookup, gdal, np
    )
    zonal_rows = _zonal_rows(features, conditions, zonal, zone_totals)
    csv_path = output_folder / f"{stem}_CN_por_subcuenca.csv"
    gpkg_path = output_folder / f"{stem}_subcuencas_CN.gpkg"
    metadata_path = output_folder / f"{stem}_metadatos.json"
    report_path = output_folder / f"{stem}_informe.html"
    _write_csv(csv_path, zonal_rows)
    _write_geopackage(gpkg_path, features, zonal_rows, spatial_reference, ogr)
    metadata = {
        "application": "HidroCN - Curva Numero",
        "method": "Cruce local LULC-HSG compatible con tabla HEC-GeoHMS",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "lulc": payload["lulc_path"], "hsg": payload["hsg_path"],
            "lookup_csv": payload["lookup_csv"], "subbasin_id_field": payload.get("id_field", ""),
        },
        "grid": {"crs": payload["output_crs"], "resolution_m": resolution, "columns": columns, "rows": rows, "bounds": bounds},
        "lookup_rows": rows_lookup,
        "quality_control": qc,
        "subbasin_statistics": zonal_rows,
        "outputs": {condition: str(path) for condition, path in output_paths.items()},
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(report_path, metadata)
    try:
        zones_path.unlink()
    except OSError:
        pass
    output_items = []
    for condition, path in output_paths.items():
        stats = global_stats[condition]
        stats["coverage_pct"] = 100.0 * qc["matched_pixels"] / max(1, sum(zone_totals.values()))
        output_items.append({
            "condition": condition, "path": str(path), "statistics": stats,
            "derived": condition != "II", "source": "local_lulc_hsg",
        })
    return {
        "outputs": output_items,
        "aligned_lulc": str(lulc_aligned), "aligned_hsg": str(hsg_aligned),
        "subbasins_gpkg": str(gpkg_path), "statistics_csv": str(csv_path),
        "report_path": str(report_path), "metadata_path": str(metadata_path),
        "quality_control": qc,
    }
