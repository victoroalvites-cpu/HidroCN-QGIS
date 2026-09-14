"""Comprueba la carga del complemento desde una extracción del ZIP final."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: zip_install_smoke.py <carpeta_que_contiene_hidro_cn_qgis>")
    package_parent = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(package_parent))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    dll_handles = []
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
                    dll_handles.append(os.add_dll_directory(str(folder)))

    from qgis.core import QgsApplication

    app = QgsApplication([], False)
    app.initQgis()
    try:
        import hidro_cn_qgis
        from hidro_cn_qgis.dialog import HidroCnDialog

        loaded_from = Path(hidro_cn_qgis.__file__).resolve()
        if package_parent not in loaded_from.parents:
            raise AssertionError(f"Se cargo otra copia del complemento: {loaded_from}")
        dialog = HidroCnDialog(None)
        assert dialog.windowTitle() == "HidroCN - Curva Numero"
        assert dialog.method_tabs.count() == 2
        dialog.close()
        print(f"HIDROCN_ZIP_INSTALL_SMOKE=OK ({loaded_from})")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
