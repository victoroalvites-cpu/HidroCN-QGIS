"""Construye y valida el ZIP instalable de HidroCN para QGIS."""

from __future__ import annotations

import configparser
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.5.0"
DIST = ROOT / "dist"
ZIP_PATH = DIST / f"HidroCN_QGIS_v{VERSION}.zip"

RUNTIME_FILES = (
    "__init__.py",
    "plugin.py",
    "dialog.py",
    "cn_table_dialog.py",
    "gee_service.py",
    "gee_auth_helper.py",
    "gee_worker_helper.py",
    "local_cn_service.py",
    "metadata.txt",
    "icon.png",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "requirements-gee.txt",
    "docs/Manual_Tecnico_y_de_Usuario_HidroCN_QGIS_v0.5.0.docx",
    "core/__init__.py",
    "core/cn_conditions.py",
    "core/cn_catalog.py",
    "core/local_cn.py",
    "core/spatial_reference.py",
)


def validate_sources():
    missing = [name for name in RUNTIME_FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Faltan archivos: " + ", ".join(missing))
    parser = configparser.ConfigParser()
    parser.read(ROOT / "metadata.txt", encoding="utf-8")
    general = parser["general"]
    if general.get("version") != VERSION:
        raise SystemExit("metadata.txt no corresponde a la version de empaquetado.")
    if general.getboolean("experimental", fallback=True):
        raise SystemExit("La version publica no puede estar marcada como experimental.")
    for key in ("homepage", "repository", "tracker", "license"):
        if not general.get(key, "").strip():
            raise SystemExit(f"Falta el metadato publico {key}.")


def build():
    validate_sources()
    DIST.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in RUNTIME_FILES:
            source = ROOT / relative
            archive.write(source, (Path(ROOT.name) / relative).as_posix())

    with zipfile.ZipFile(ZIP_PATH) as archive:
        names = archive.namelist()
        prefix = ROOT.name + "/"
        if not names or any(not name.startswith(prefix) for name in names):
            raise SystemExit("El ZIP no tiene una unica carpeta raiz hidro_cn_qgis.")
        forbidden = ("__pycache__", ".pyc", ".pyo", ".git/", "/build/", "/tests/")
        unexpected = [name for name in names if any(token in name for token in forbidden)]
        if unexpected:
            raise SystemExit("Archivos prohibidos en ZIP: " + ", ".join(unexpected))
        metadata = archive.read(prefix + "metadata.txt").decode("utf-8")
        if "version=0.5.0" not in metadata or "experimental=False" not in metadata:
            raise SystemExit("Los metadatos internos del ZIP no son publicables.")

    size = ZIP_PATH.stat().st_size
    if size > 25 * 1024 * 1024:
        raise SystemExit("El ZIP supera el limite de 25 MB del portal QGIS.")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"ZIP={ZIP_PATH}")
    print(f"FILES={len(RUNTIME_FILES)}")
    print(f"SIZE={size}")
    print(f"SHA256={digest}")


if __name__ == "__main__":
    build()
