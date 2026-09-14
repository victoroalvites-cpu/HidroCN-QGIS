"""Conversiones de numero de curva entre condiciones antecedentes.

CN-II es la condicion normal o promedio. Las relaciones (1) y (2) publicadas
por ANA (2015) se aplican celda por celda para estimar CN-I y CN-III. Los
productos derivados siempre deben conservar esa indicacion en sus metadatos.
"""

from __future__ import annotations

import math


CONDITION_LABELS = {
    "I": "seca derivada",
    "II": "normal",
    "III": "humeda derivada",
}


def validate_cn(value: float) -> float:
    """Devuelve un CN finito dentro del intervalo fisico (0, 100]."""

    try:
        cn = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("El numero de curva debe ser numerico.") from error
    if not math.isfinite(cn) or not 0.0 < cn <= 100.0:
        raise ValueError("El numero de curva debe estar en el intervalo (0, 100].")
    return cn


def cn_dry_from_normal(cn_ii: float) -> float:
    """Convierte CN-II a CN-I (condicion seca)."""

    cn = validate_cn(cn_ii)
    return min(100.0, (4.2 * cn) / (10.0 - 0.058 * cn))


def cn_wet_from_normal(cn_ii: float) -> float:
    """Convierte CN-II a CN-III (condicion humeda)."""

    cn = validate_cn(cn_ii)
    return min(100.0, (23.0 * cn) / (10.0 + 0.13 * cn))


def derive_cn_conditions(cn_ii: float) -> dict[str, float]:
    """Genera CN-I, CN-II y CN-III a partir de la condicion normal."""

    normal = validate_cn(cn_ii)
    return {
        "I": cn_dry_from_normal(normal),
        "II": normal,
        "III": cn_wet_from_normal(normal),
    }
