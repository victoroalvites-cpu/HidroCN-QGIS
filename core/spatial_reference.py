"""Ayudas puras para seleccionar un SRC proyectado."""

from __future__ import annotations

import math


def utm_zone(longitude: float) -> int:
    """Calcula la zona UTM 1..60 a partir de una longitud WGS 84."""

    lon = float(longitude)
    if not math.isfinite(lon) or lon < -180.0 or lon > 180.0:
        raise ValueError("La longitud debe estar entre -180 y 180 grados.")
    if lon == 180.0:
        return 60
    return max(1, min(60, int(math.floor((lon + 180.0) / 6.0)) + 1))


def suggested_utm_authid(longitude: float, latitude: float) -> str:
    """Sugiere el EPSG de WGS 84 / UTM para un punto."""

    lat = float(latitude)
    if not math.isfinite(lat) or lat < -80.0 or lat > 84.0:
        raise ValueError("UTM solo se recomienda entre 80 S y 84 N.")
    base = 32600 if lat >= 0.0 else 32700
    return f"EPSG:{base + utm_zone(longitude)}"
