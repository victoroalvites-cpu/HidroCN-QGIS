"""Ejecutor aislado para consultas y descargas Earth Engine de HidroCN."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PLUGIN_DIR.parent))

from hidro_cn_qgis.gee_service import download_cn_products, initialize_ee, inspect_source


def execute(request):
    operation = request.get("operation")
    project = request.get("project_id", "")
    connection = initialize_ee(project)
    if operation == "initialize":
        return connection
    if operation == "inspect":
        return inspect_source(
            request.get("source_key", ""),
            request.get("custom_asset", ""),
            request.get("custom_band", ""),
        )
    if operation == "download":
        return download_cn_products(
            request.get("source_key", ""),
            request.get("geometry_geojson") or {},
            request.get("conditions") or [],
            request.get("output_crs", ""),
            request.get("scale_m", 0),
            request.get("output_folder", ""),
            request.get("prefix", ""),
            request.get("custom_asset", ""),
            request.get("custom_band", ""),
            request.get("features") or [],
            request.get("id_field", ""),
        )
    raise ValueError(f"Operacion externa desconocida: {operation!r}.")


def main():
    request_path = Path(sys.argv[1])
    response_path = Path(sys.argv[2])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = {"ok": True, "result": execute(request)}
        code = 0
    except Exception as error:
        response = {
            "ok": False,
            "error_type": type(error).__name__,
            "error": str(error) or repr(error),
        }
        code = 1
    response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
