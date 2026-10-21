"""Acceso opcional a Google Earth Engine para descargar mapas de CN.

El modulo no importa QGIS y carga ``earthengine-api`` de forma diferida. El
complemento puede abrirse aunque la dependencia no este instalada. Las
credenciales son gestionadas exclusivamente por la biblioteca oficial de GEE.
"""

from __future__ import annotations

import importlib
import json
import logging
import math
import os
import re
import subprocess  # nosec B404 - solo ejecuta helpers locales con shell=False
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from .raster_blocks import read_float64_block, write_float64_block


CN_PERU_ASSET = "projects/ee-mportuguezm/assets/CN_Peru"  # pragma: allowlist secret
GCN250_AVERAGE_ASSET = "users/jaafarhadi/GCN250/GCN250Average"
GCN250_DRY_ASSET = "users/jaafarhadi/GCN250/GCN250Dry"
GCN250_WET_ASSET = "users/jaafarhadi/GCN250/GCN250Wet"

CONDITION_NAMES = {
    "I": "seca",
    "II": "normal",
    "III": "humeda",
}

ANA_FORMULAS = {
    "I": "CN_I = (4.2 * CN_II) / (10 - 0.058 * CN_II)",
    "III": "CN_III = (23 * CN_II) / (10 + 0.13 * CN_II)",
}


class GeeError(RuntimeError):
    """Error de Earth Engine listo para presentar al usuario."""


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    label: str
    assets: Mapping[str, str]
    default_band: str = ""
    nominal_scale_m: Optional[float] = None
    notes: str = ""


SOURCE_CATALOG = {
    "cn_peru": SourceDefinition(
        "cn_peru",
        "CN Peru (CN-II normal; I y III derivados)",
        {"II": CN_PERU_ASSET},
        "",
        90.0,
        "CN-I y CN-III se derivan de CN-II con las relaciones (1) y (2) de ANA (2015).",
    ),
    "gcn250": SourceDefinition(
        "gcn250",
        "GCN250 (Dry, Average y Wet nativos)",
        {
            "I": GCN250_DRY_ASSET,
            "II": GCN250_AVERAGE_ASSET,
            "III": GCN250_WET_ASSET,
        },
        "b1",
        250.0,
        "Cada condicion se obtiene de su asset GCN250 correspondiente.",
    ),
}


def _load_ee():
    required = ("Authenticate", "Initialize", "Image", "Geometry")
    try:
        module = importlib.import_module("ee")
        if all(hasattr(module, name) for name in required):
            return module
        raise ImportError("El modulo ee encontrado no es earthengine-api.")
    except ImportError as first_error:
        vendor = Path(__file__).with_name("vendor")
        if vendor.is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        for name in tuple(sys.modules):
            if name == "ee" or name.startswith("ee."):
                sys.modules.pop(name, None)
        importlib.invalidate_caches()
        try:
            module = importlib.import_module("ee")
            if not all(hasattr(module, name) for name in required):
                raise ImportError("La dependencia incluida no contiene Earth Engine.")
            return module
        except ImportError as error:
            raise GeeError(
                "No se encontro earthengine-api. Instalela en el Python de QGIS y reinicie QGIS. "
                "El metodo local LULC-HSG funciona sin esta biblioteca."
            ) from (error or first_error)


def dependency_status() -> dict[str, object]:
    try:
        ee = _load_ee()
        return {"available": True, "version": getattr(ee, "__version__", "desconocida")}
    except Exception as error:
        return {"available": False, "error": str(error)}


def initialize_ee(project_id: str) -> dict[str, object]:
    project = str(project_id or "").strip()
    if not project:
        raise GeeError("Ingrese el ID del proyecto de Google Cloud.")
    ee = _load_ee()
    try:
        ee.Initialize(project=project)
        if hasattr(ee.data, "setDeadline"):
            ee.data.setDeadline(60000)
        value = ee.String("conexion_correcta").getInfo()
    except Exception as error:
        detail = str(error).strip() or repr(error)
        raise GeeError(
            "No fue posible inicializar Earth Engine. Use 'Conectar / autorizar' y verifique "
            f"el proyecto y el acceso a los assets. Detalle: {detail}"
        ) from error
    return {
        "project": project,
        "test": value,
        "api_version": getattr(ee, "__version__", ""),
    }


def authenticate_ee(project_id: str, force: bool = False) -> dict[str, object]:
    project = str(project_id or "").strip()
    if not project:
        raise GeeError("Ingrese el ID del proyecto de Google Cloud.")
    ee = _load_ee()
    if not force:
        try:
            ee.Initialize(project=project)
            ee.Number(1).getInfo()
            return {"project": project, "authenticated": True, "reused": True}
        except Exception:
            logging.getLogger(__name__).debug(
                "Las credenciales existentes de GEE no se pudieron reutilizar.",
                exc_info=True,
            )
    try:
        ee.Authenticate(auth_mode="localhost:0", force=force)
        ee.Initialize(project=project)
        ee.Number(1).getInfo()
    except Exception as error:
        raise GeeError(
            "La autorizacion de Earth Engine no termino correctamente. Complete el flujo en "
            f"el navegador con su propia cuenta. Detalle: {error}"
        ) from error
    return {"project": project, "authenticated": True, "reused": False}


def authenticate_ee_external(
    project_id: str,
    force: bool = False,
    timeout_seconds: float = 180.0,
    cancel_check=None,
) -> dict[str, object]:
    project = str(project_id or "").strip()
    if not project:
        raise GeeError("Ingrese el ID del proyecto de Google Cloud.")
    helper = Path(__file__).with_name("gee_auth_helper.py")
    python_executable = Path(sys.prefix) / ("python.exe" if os.name == "nt" else "bin/python")
    if not python_executable.is_file():
        raise GeeError(f"No se encontro el Python de QGIS en {python_executable}.")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    process = subprocess.Popen(  # nosec B603 - argumentos cerrados, sin shell
        [str(python_executable), str(helper), project, "1" if force else "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    started = time.monotonic()
    while process.poll() is None:
        if cancel_check is not None and cancel_check():
            process.terminate()
            raise GeeError("Autenticacion cancelada por el usuario.")
        if time.monotonic() - started > timeout_seconds:
            process.terminate()
            raise GeeError("La autenticacion supero el tiempo permitido.")
        time.sleep(0.2)
    stdout, stderr = process.communicate()
    marker = "HIDROCN_GEE_RESULT="
    result_line = next(
        (line for line in reversed(stdout.splitlines()) if line.startswith(marker)), ""
    )
    if process.returncode != 0 or not result_line:
        detail = (stderr or stdout or "El proceso no devolvio un resultado.").strip()
        raise GeeError(f"No se completo la autenticacion. Detalle: {detail[-2000:]}")
    try:
        return json.loads(result_line[len(marker):])
    except json.JSONDecodeError as error:
        raise GeeError("La respuesta del proceso de autenticacion no fue valida.") from error


def run_gee_external(
    operation: str,
    payload: Mapping[str, object],
    timeout_seconds: float = 600.0,
    cancel_check=None,
    progress_callback=None,
):
    helper = Path(__file__).with_name("gee_worker_helper.py")
    python_executable = Path(sys.prefix) / ("python.exe" if os.name == "nt" else "bin/python")
    if not python_executable.is_file():
        raise GeeError(f"No se encontro el Python de QGIS en {python_executable}.")
    request = dict(payload)
    request["operation"] = str(operation)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="hidrocn_gee_") as folder:
        request_path = Path(folder) / "request.json"
        response_path = Path(folder) / "response.json"
        progress_path = Path(folder) / "progress.jsonl"
        stdout_path = Path(folder) / "stdout.log"
        stderr_path = Path(folder) / "stderr.log"
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        stdout_file = stdout_path.open("wb")
        stderr_file = stderr_path.open("wb")
        try:
            process = subprocess.Popen(  # nosec B603 - argumentos cerrados, sin shell
                [str(python_executable), str(helper), str(request_path), str(response_path)],
                stdout=stdout_file,
                stderr=stderr_file,
                creationflags=creationflags,
            )
            started = time.monotonic()
            progress_offset = 0

            def read_progress():
                nonlocal progress_offset
                if progress_callback is None or not progress_path.is_file():
                    return
                with progress_path.open("r", encoding="utf-8") as stream:
                    stream.seek(progress_offset)
                    while True:
                        line_start = stream.tell()
                        line = stream.readline()
                        if not line:
                            break
                        if not line.endswith("\n"):
                            stream.seek(line_start)
                            break
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        progress_callback(event)
                    progress_offset = stream.tell()

            def stop_process():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            while process.poll() is None:
                read_progress()
                if cancel_check is not None and cancel_check():
                    stop_process()
                    raise GeeError("Operacion Earth Engine cancelada por el usuario.")
                if time.monotonic() - started > timeout_seconds:
                    stop_process()
                    raise GeeError("La operacion Earth Engine supero el tiempo permitido.")
                time.sleep(0.2)
            process.wait()
        finally:
            stdout_file.close()
            stderr_file.close()
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        read_progress()
        if not response_path.is_file():
            detail = (stderr or stdout or "El proceso externo no genero respuesta.").strip()
            raise GeeError(f"Fallo el proceso externo de Earth Engine: {detail[-2000:]}")
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if process.returncode != 0 or not response.get("ok"):
            error_type = response.get("error_type", "Error")
            detail = response.get("error") or stderr or stdout or "Sin detalle"
            if stderr and stderr.strip() not in str(detail):
                detail = f"{detail} | Diagnostico del proceso: {stderr.strip()[-2000:]}"
            raise GeeError(f"{error_type}: {detail}")
        return response.get("result")


def _source(source_key: str, custom_asset: str = "", custom_band: str = "") -> SourceDefinition:
    key = str(source_key or "").strip()
    if key == "custom":
        asset = str(custom_asset or "").strip()
        if not asset:
            raise GeeError("Ingrese el ID del asset personalizado.")
        return SourceDefinition(
            "custom",
            "Asset personalizado (interpretado como CN-II)",
            {"II": asset},
            str(custom_band or "").strip(),
            None,
            "El usuario declaro que el asset representa CN-II normal.",
        )
    try:
        return SOURCE_CATALOG[key]
    except KeyError as error:
        raise GeeError(f"Fuente de CN desconocida: {source_key!r}.") from error


def _first_band(image, band_name: str):
    return image.select([band_name]) if band_name else image.select([0])


def _condition_image(ee, definition: SourceDefinition, condition: str):
    if condition in definition.assets:
        asset = definition.assets[condition]
        image = _first_band(ee.Image(asset), definition.default_band)
        image = image.toFloat()
        valid_mask = image.mask().And(image.gt(0)).And(image.lte(100))
        return image.updateMask(valid_mask).rename(f"CN_{condition}"), asset, False

    normal_asset = definition.assets.get("II")
    if not normal_asset:
        raise GeeError(f"La fuente {definition.label} no permite generar CN-{condition}.")
    normal = _first_band(ee.Image(normal_asset), definition.default_band).toFloat()
    normal = normal.updateMask(normal.mask().And(normal.gt(0)).And(normal.lte(100)))
    if condition == "I":
        image = normal.expression(
            "(4.2 * cn) / (10 - 0.058 * cn)", {"cn": normal}
        )
    elif condition == "III":
        image = normal.expression(
            "(23 * cn) / (10 + 0.13 * cn)", {"cn": normal}
        )
    else:
        raise GeeError(f"Condicion antecedente desconocida: {condition!r}.")
    image = image.updateMask(normal.mask()).clamp(0, 100).toFloat()
    return image.rename(f"CN_{condition}"), normal_asset, True


def _validated_conditions(conditions: Sequence[str]) -> list[str]:
    requested = []
    for value in conditions:
        condition = str(value).upper().strip()
        if condition not in CONDITION_NAMES:
            raise GeeError(f"Condicion antecedente desconocida: {condition!r}.")
        if condition not in requested:
            requested.append(condition)
    if not requested:
        raise GeeError("Seleccione al menos una condicion antecedente.")
    return [condition for condition in ("I", "II", "III") if condition in requested]


def inspect_source(
    source_key: str,
    custom_asset: str = "",
    custom_band: str = "",
) -> dict[str, object]:
    ee = _load_ee()
    definition = _source(source_key, custom_asset, custom_band)
    assets = {}
    for condition, asset in definition.assets.items():
        image = ee.Image(asset)
        selected = _first_band(image, definition.default_band)
        try:
            assets[condition] = {
                "asset": asset,
                "bands": image.bandNames().getInfo(),
                "projection": selected.projection().crs().getInfo(),
                "nominal_scale_m": selected.projection().nominalScale().getInfo(),
            }
        except Exception as error:
            raise GeeError(
                f"No se pudo leer el asset {asset}. Compruebe que exista y que su cuenta tenga acceso. "
                f"Detalle: {error}"
            ) from error
    return {
        "key": definition.key,
        "label": definition.label,
        "assets": assets,
        "notes": definition.notes,
    }


def _safe_prefix(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return text or "hidrocn"


def _available_path(path: Path) -> Path:
    """Evita sobrescribir o chocar con un raster que QGIS mantiene abierto."""

    if not path.exists():
        return path
    for number in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise GeeError(f"No se encontro un nombre de salida disponible para {path.name}.")


def _validated_gee_download_url(url: str) -> str:
    """Acepta solo URLs HTTPS emitidas por la infraestructura de Google."""

    value = str(url or "").strip()
    parsed = urllib.parse.urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    allowed_host = any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in ("googleapis.com", "googleusercontent.com")
    )
    if parsed.scheme.lower() != "https" or not allowed_host:
        raise GeeError("Earth Engine devolvio una URL de descarga no permitida.")
    return value


def _download_url_to_tif(url: str, destination: Path) -> None:
    part = destination.with_suffix(destination.suffix + ".part")
    safe_url = _validated_gee_download_url(url)
    request = urllib.request.Request(safe_url, headers={"User-Agent": "HidroCN-QGIS/0.5.3"})
    try:
        # B310: safe_url ya exige HTTPS y un dominio de descarga de Google.
        with urllib.request.urlopen(request, timeout=300) as response, part.open("wb") as output:  # nosec B310
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
        with part.open("rb") as handle:
            signature = handle.read(4)
        if signature[:2] == b"PK":
            with zipfile.ZipFile(part) as archive:
                candidates = [name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))]
                if len(candidates) != 1:
                    raise GeeError("La descarga ZIP de GEE no contiene un unico GeoTIFF.")
                member = candidates[0]
                with archive.open(member) as source, destination.open("wb") as target:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        target.write(block)
            part.unlink(missing_ok=True)
        else:
            os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def normalize_geotiff_nodata(
    path: str,
    geometry_geojson: Optional[Mapping[str, object]] = None,
    nodata: float = -9999.0,
    progress_callback=None,
) -> dict[str, object]:
    """Recorta localmente la cuenca y declara NoData GDAL real.

    Las descargas ``getDownloadURL`` de imagenes flotantes pueden codificar la
    mascara externa como ``-inf`` o incluso conservar valores fuera del poligono
    en imagenes derivadas. QGIS entonces la incluye en valores unicos y pinta el
    rectangulo de la extension. Se rasteriza de nuevo la geometria WGS 84 sobre
    la cuadricula descargada y la normalizacion se hace por bloques.
    """

    def report(stage):
        if progress_callback is not None:
            progress_callback(stage)

    report("cargando GDAL y NumPy")
    try:
        import numpy as np
        from osgeo import gdal, ogr, osr
    except ImportError as error:
        raise GeeError(
            "No se encontraron GDAL y NumPy en el Python de QGIS para normalizar NoData."
        ) from error

    if hasattr(gdal, "UseExceptions"):
        gdal.UseExceptions()

    report("abriendo el GeoTIFF")
    target = Path(path)
    dataset = gdal.Open(str(target), gdal.GA_Update)
    if dataset is None:
        raise GeeError(f"GDAL no pudo abrir el GeoTIFF descargado: {target}")
    geometry_mask_dataset = None
    vector_dataset = None
    replaced = 0
    valid_count = 0
    inside_count = 0
    value_sum = 0.0
    minimum = math.inf
    maximum = -math.inf
    basin_area_km2 = None
    try:
        if geometry_geojson:
            report("preparando la mascara de la cuenca")
            geometry = ogr.CreateGeometryFromJson(json.dumps(dict(geometry_geojson)))
            if geometry is None or geometry.IsEmpty():
                raise GeeError("GDAL no pudo interpretar la geometria GeoJSON de la cuenca.")
            source_srs = osr.SpatialReference()
            source_srs.ImportFromEPSG(4326)
            target_srs = osr.SpatialReference()
            target_srs.ImportFromWkt(dataset.GetProjection())
            if hasattr(source_srs, "SetAxisMappingStrategy"):
                source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            geometry.Transform(osr.CoordinateTransformation(source_srs, target_srs))
            basin_area_km2 = geometry.GetArea() / 1_000_000.0

            geometry_mask_dataset = gdal.GetDriverByName("MEM").Create(
                "", dataset.RasterXSize, dataset.RasterYSize, 1, gdal.GDT_Byte
            )
            geometry_mask_dataset.SetGeoTransform(dataset.GetGeoTransform())
            geometry_mask_dataset.SetProjection(dataset.GetProjection())
            geometry_mask_band = geometry_mask_dataset.GetRasterBand(1)
            geometry_mask_band.Fill(0)

            vector_driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
            vector_dataset = vector_driver.CreateDataSource("")
            vector_layer = vector_dataset.CreateLayer(
                "cuenca", srs=target_srs, geom_type=geometry.GetGeometryType()
            )
            feature = ogr.Feature(vector_layer.GetLayerDefn())
            feature.SetGeometry(geometry)
            vector_layer.CreateFeature(feature)
            feature = None
            gdal.RasterizeLayer(
                geometry_mask_dataset,
                [1],
                vector_layer,
                burn_values=[1],
            )

        report("leyendo pixeles y calculando estadisticos")
        for band_index in range(1, dataset.RasterCount + 1):
            band = dataset.GetRasterBand(band_index)
            block_x, block_y = band.GetBlockSize()
            block_x = block_x or min(512, dataset.RasterXSize)
            block_y = block_y or min(512, dataset.RasterYSize)
            for y_offset in range(0, dataset.RasterYSize, block_y):
                rows = min(block_y, dataset.RasterYSize - y_offset)
                for x_offset in range(0, dataset.RasterXSize, block_x):
                    columns = min(block_x, dataset.RasterXSize - x_offset)
                    values = read_float64_block(
                        band, x_offset, y_offset, columns, rows, np, gdal
                    )
                    invalid = (~np.isfinite(values)) | (values <= 0) | (values > 100)
                    if geometry_mask_dataset is not None:
                        inside = read_float64_block(
                            geometry_mask_dataset.GetRasterBand(1),
                            x_offset, y_offset, columns, rows, np, gdal,
                        )
                        inside_count += int(np.count_nonzero(inside))
                        invalid |= inside == 0
                    else:
                        inside_count += int(values.size)
                    valid = values[~invalid]
                    if valid.size:
                        valid_count += int(valid.size)
                        value_sum += float(valid.sum(dtype=np.float64))
                        minimum = min(minimum, float(valid.min()))
                        maximum = max(maximum, float(valid.max()))
                    count = int(np.count_nonzero(invalid))
                    if count:
                        values[invalid] = nodata
                        write_float64_block(band, x_offset, y_offset, values, gdal)
                        replaced += count
            band.SetNoDataValue(float(nodata))
            band.FlushCache()
        # Los estadisticos ya se calcularon sobre los pixeles validos. Una
        # segunda lectura completa con ComputeStatistics puede bloquearse en
        # algunos GeoTIFF abiertos en modo de actualizacion y no aporta datos.
        report("guardando NoData y cerrando el GeoTIFF")
        dataset.FlushCache()
    finally:
        dataset = None
        geometry_mask_dataset = None
        vector_dataset = None
    report("estadisticos locales terminados")
    return {
        "path": str(target),
        "nodata": float(nodata),
        "replaced_pixels": replaced,
        "statistics": {
            "minimum": minimum if valid_count else None,
            "maximum": maximum if valid_count else None,
            "mean": value_sum / valid_count if valid_count else None,
            "coverage_pct": 100.0 * valid_count / inside_count if inside_count else 0.0,
            "basin_area_km2": basin_area_km2,
            "valid_pixels": valid_count,
            "basin_pixels": inside_count,
        },
    }


def download_cn_products(
    source_key: str,
    geometry_geojson: Mapping[str, object],
    conditions: Sequence[str],
    output_crs: str,
    scale_m: float,
    output_folder: str,
    prefix: str,
    custom_asset: str = "",
    custom_band: str = "",
    subbasins: Optional[Sequence[Mapping[str, object]]] = None,
    subbasin_id_field: str = "",
    progress_callback=None,
) -> dict[str, object]:
    ee = _load_ee()
    definition = _source(source_key, custom_asset, custom_band)
    selected_conditions = _validated_conditions(conditions)
    crs = str(output_crs or "").strip().upper()
    if not re.fullmatch(r"EPSG:\d+", crs):
        raise GeeError("El SRC de salida debe tener un codigo EPSG valido.")
    try:
        scale = float(scale_m)
    except (TypeError, ValueError) as error:
        raise GeeError("La resolucion de salida debe ser numerica.") from error
    if not math.isfinite(scale) or scale <= 0:
        raise GeeError("La resolucion de salida debe ser mayor que cero.")
    if not isinstance(geometry_geojson, Mapping) or not geometry_geojson.get("coordinates"):
        raise GeeError("La geometria GeoJSON de la cuenca no es valida.")

    geometry = ee.Geometry(dict(geometry_geojson))
    output_dir = Path(output_folder).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = _safe_prefix(prefix)
    outputs = []
    metadata_path = _available_path(output_dir / f"{file_prefix}_CN_metadatos.json")
    statistics_csv = _available_path(output_dir / f"{file_prefix}_CN_por_subcuenca.csv") if subbasins else None
    subbasins_gpkg = _available_path(output_dir / f"{file_prefix}_subcuencas_CN.gpkg") if subbasins else None
    areal_result = None

    def report(percent, message):
        if progress_callback is not None:
            progress_callback(int(percent), str(message))

    def save_metadata(status):
        metadata = {
            "schema": 2,
            "application": "HidroCN - Curva Numero",
            "version": "0.5.3",
            "status": status,
            "source_key": definition.key,
            "source_label": definition.label,
            "source_notes": definition.notes,
            "output_crs": crs,
            "scale_m": scale,
            "statistics_method": "local_final_geotiff",
            "coverage_pct_definition": "valid_pixels / basin_pixels on the output grid",
            "conditions": outputs,
            "subbasin_id_field": subbasin_id_field,
            "subbasin_statistics": areal_result["rows"] if areal_result else [],
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    for index, condition in enumerate(selected_conditions):
        base_progress = 100.0 * index / len(selected_conditions)
        step = 100.0 / len(selected_conditions)
        report(base_progress, f"CN-{condition}: preparando imagen en Earth Engine")
        image, asset, derived = _condition_image(ee, definition, condition)
        image = image.updateMask(image.gt(0).And(image.lte(100))).clip(geometry)
        filename = f"{file_prefix}_CN_{condition}_{CONDITION_NAMES[condition]}.tif"
        target = _available_path(output_dir / filename)
        staged = target.with_suffix(target.suffix + ".processing")
        params = {
            "name": target.stem,
            "region": geometry,
            "scale": scale,
            "crs": crs,
            "format": "GEO_TIFF",
            "filePerBand": False,
        }
        stage = "generando la descarga"
        try:
            report(base_progress + step * 0.15, f"CN-{condition}: generando enlace de descarga")
            url = image.getDownloadURL(params)
            stage = "transfiriendo el GeoTIFF"
            report(base_progress + step * 0.35, f"CN-{condition}: transfiriendo GeoTIFF")
            _download_url_to_tif(url, staged)
            stage = "normalizando el raster"
            report(base_progress + step * 0.55, f"CN-{condition}: normalizando NoData y calculando estadisticos locales")
            nodata_info = normalize_geotiff_nodata(
                str(staged),
                geometry_geojson,
                progress_callback=lambda stage: report(
                    base_progress + step * 0.6,
                    f"CN-{condition}: {stage}",
                ),
            )
            statistics = nodata_info["statistics"]
            staged.replace(target)
            nodata_info["path"] = str(target)
        except Exception as error:
            staged.unlink(missing_ok=True)
            staged.with_suffix(staged.suffix + ".part").unlink(missing_ok=True)
            raise GeeError(
                f"No se pudo completar CN-{condition} mientras se estaba {stage}. "
                f"Detalle: {error}"
            ) from error
        outputs.append(
            {
                "condition": condition,
                "condition_name": CONDITION_NAMES[condition],
                "path": str(target),
                "asset": asset,
                "derived": derived,
                "formula": ANA_FORMULAS.get(condition) if derived else None,
                "statistics": statistics,
                "nodata": {key: value for key, value in nodata_info.items() if key != "statistics"},
            }
        )
        save_metadata("partial")
        if subbasins:
            report(base_progress + step * 0.8, f"CN-{condition}: calculando resumen por subcuenca")
            try:
                from .local_cn_service import summarize_cn_rasters

                temporary_csv = statistics_csv.with_name(statistics_csv.stem + ".processing.csv")
                temporary_gpkg = subbasins_gpkg.with_name(subbasins_gpkg.stem + ".processing.gpkg")
                temporary_csv.unlink(missing_ok=True)
                temporary_gpkg.unlink(missing_ok=True)
                partial = summarize_cn_rasters(
                    subbasins, outputs, crs, temporary_csv, temporary_gpkg
                )
                temporary_csv.replace(statistics_csv)
                temporary_gpkg.replace(subbasins_gpkg)
                areal_result = {
                    **partial,
                    "statistics_csv": str(statistics_csv),
                    "subbasins_gpkg": str(subbasins_gpkg),
                }
                save_metadata("partial")
            except Exception as error:
                raise GeeError(
                    "El raster y sus estadisticos locales se guardaron, pero fallo el "
                    f"resumen por subcuenca. Detalle: {error}"
                ) from error
        report(base_progress + step, f"CN-{condition}: raster y estadisticos guardados")

    save_metadata("complete")
    report(100, "Todos los productos CN estan completos")
    result = {"outputs": outputs, "metadata_path": str(metadata_path)}
    if areal_result:
        result.update(
            {
                "statistics_csv": areal_result["statistics_csv"],
                "subbasins_gpkg": areal_result["subbasins_gpkg"],
                "subbasin_statistics": areal_result["rows"],
            }
        )
    return result
