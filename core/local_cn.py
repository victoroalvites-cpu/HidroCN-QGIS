"""Nucleo puro del calculo local SCS-CN.

La tabla principal sigue el esquema usado por HEC-GeoHMS::

    LUValue,Description,A,B,C,D

Tambien se aceptan los encabezados de SCS-CN Builder
(``LULC_code,CN_A,CN_B,CN_C,CN_D``). Los catalogos incluidos son una ayuda
para construir la tabla; nunca asignan automaticamente los codigos propios de
una leyenda de uso del suelo.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


LOOKUP_HEADERS = ("LUValue", "Description", "A", "B", "C", "D")
GROUPS = ("A", "B", "C", "D")

_ALIASES = {
    "lu": ("LUValue", "LULC_code", "LU_VALUE", "lulc", "value", "codigo"),
    "description": ("Description", "Class", "Descripcion", "descripcion", "label"),
    "A": ("A", "CN_A", "CNA"),
    "B": ("B", "CN_B", "CNB"),
    "C": ("C", "CN_C", "CNC"),
    "D": ("D", "CN_D", "CND"),
}


def _field_name(fieldnames, aliases):
    normalized = {str(name).strip().lower(): name for name in (fieldnames or [])}
    for alias in aliases:
        found = normalized.get(alias.lower())
        if found is not None:
            return found
    return None


def _integer_code(value, label):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} debe ser un codigo entero: {value!r}.") from error
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{label} debe ser un codigo entero: {value!r}.")
    return int(number)


def _cn_value(value, label):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} debe ser numerico: {value!r}.") from error
    if not math.isfinite(number) or not 0.0 < number <= 100.0:
        raise ValueError(f"{label} debe estar en el intervalo (0, 100].")
    return number


def _optional_cn_value(value, label):
    if value is None or not str(value).strip():
        return None
    return _cn_value(value, label)


def read_lookup_csv(path):
    """Lee y valida una tabla CN-II, devolviendo filas y diccionario de cruce."""

    csv_path = Path(path)
    if not csv_path.is_file():
        raise ValueError(f"No existe la tabla CN: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        resolved = {key: _field_name(fields, aliases) for key, aliases in _ALIASES.items()}
        missing = [key for key in ("lu", "A", "B", "C", "D") if not resolved[key]]
        if missing:
            raise ValueError(
                "La tabla CN debe contener LUValue,A,B,C,D (HEC-GeoHMS) o "
                "LULC_code,CN_A,CN_B,CN_C,CN_D."
            )

        rows = []
        lookup = {}
        for line_number, raw in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in raw.values()):
                continue
            lu_code = _integer_code(raw[resolved["lu"]], f"LUValue (fila {line_number})")
            if lu_code in {row["lu_value"] for row in rows}:
                raise ValueError(f"LUValue duplicado en la fila {line_number}: {lu_code}.")
            description_field = resolved.get("description")
            description = str(raw.get(description_field, "") or "").strip()
            values = {}
            for group_index, group in enumerate(GROUPS, start=1):
                cn = _optional_cn_value(
                    raw[resolved[group]], f"CN-{group} (fila {line_number})"
                )
                values[group] = cn
                if cn is not None:
                    lookup[(lu_code, group_index)] = cn
            if not any(values.values()):
                raise ValueError(
                    f"La fila {line_number} no contiene ningun valor CN entre A y D."
                )
            rows.append({"lu_value": lu_code, "description": description, **values})

    if not rows:
        raise ValueError("La tabla CN no contiene filas de datos.")
    return rows, lookup


def write_lookup_template(path):
    """Crea una plantilla HEC-GeoHMS sin asignaciones cientificas implicitas."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream).writerow(LOOKUP_HEADERS)
    return str(output)


def build_cn_arrays(lulc, hsg, lookup, nodata=-9999.0, basin_mask=None):
    """Cruza codigos LULC/HSG y devuelve CN-I, II, III y control de calidad."""

    import numpy as np

    lulc_array = np.asarray(lulc)
    hsg_array = np.asarray(hsg)
    if lulc_array.shape != hsg_array.shape:
        raise ValueError("Los raster de uso del suelo y HSG no comparten la misma malla.")
    valid = np.isfinite(lulc_array) & np.isfinite(hsg_array)
    valid &= lulc_array != nodata
    valid &= hsg_array != nodata
    if basin_mask is not None:
        valid &= np.asarray(basin_mask).astype(bool)

    integer_codes = np.isclose(lulc_array, np.rint(lulc_array), atol=1e-6)
    integer_hsg = np.isclose(hsg_array, np.rint(hsg_array), atol=1e-6)
    valid &= integer_codes & integer_hsg

    cn_ii = np.full(lulc_array.shape, nodata, dtype=np.float32)
    matched = np.zeros(lulc_array.shape, dtype=bool)
    for (lu_code, hsg_code), cn in lookup.items():
        mask = valid & (lulc_array == lu_code) & (hsg_array == hsg_code)
        cn_ii[mask] = cn
        matched |= mask

    cn_i = np.full(lulc_array.shape, nodata, dtype=np.float32)
    cn_iii = np.full(lulc_array.shape, nodata, dtype=np.float32)
    cn_i[matched] = (4.2 * cn_ii[matched]) / (10.0 - 0.058 * cn_ii[matched])
    cn_iii[matched] = (23.0 * cn_ii[matched]) / (10.0 + 0.13 * cn_ii[matched])
    cn_i[matched] = np.clip(cn_i[matched], 0.0, 100.0)
    cn_iii[matched] = np.clip(cn_iii[matched], 0.0, 100.0)

    unmatched = valid & ~matched
    unknown_lulc = sorted(int(value) for value in np.unique(lulc_array[unmatched]))
    unknown_hsg = sorted(int(value) for value in np.unique(hsg_array[unmatched]))
    unexpected_hsg = sorted(
        int(value) for value in np.unique(hsg_array[valid]) if int(value) not in (1, 2, 3, 4)
    )
    qc = {
        "valid_input_pixels": int(np.count_nonzero(valid)),
        "matched_pixels": int(np.count_nonzero(matched)),
        "unmatched_pixels": int(np.count_nonzero(unmatched)),
        "outside_or_nodata_pixels": int(valid.size - np.count_nonzero(valid)),
        "unknown_lulc_values": unknown_lulc,
        "unknown_hsg_values": unknown_hsg,
        "unexpected_hsg_values": unexpected_hsg,
    }
    return {"I": cn_i, "II": cn_ii, "III": cn_iii}, qc
