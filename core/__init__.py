"""Calculos puros y reutilizables de HidroCN."""

from .cn_conditions import CONDITION_LABELS, derive_cn_conditions
from .spatial_reference import suggested_utm_authid

__all__ = ["CONDITION_LABELS", "derive_cn_conditions", "suggested_utm_authid"]
