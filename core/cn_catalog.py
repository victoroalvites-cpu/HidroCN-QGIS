"""Catalogos trazables de numero de curva para construir tablas HEC-GeoHMS.

Los codigos de un raster de cobertura son propios de cada producto. Por ello los
catalogos no asignan codigos automaticamente: el usuario relaciona cada valor
``LUValue`` con una cobertura, tratamiento y condicion hidrologica documentada.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogEntry:
    key: str
    cover: str
    treatment: str
    condition: str
    a: int | None
    b: int | None
    c: int | None
    d: int | None

    @property
    def label(self):
        details = [self.cover]
        if self.treatment:
            details.append(self.treatment)
        if self.condition:
            details.append(self.condition)
        return " | ".join(details)

    @property
    def values(self):
        return {"A": self.a, "B": self.b, "C": self.c, "D": self.d}


@dataclass(frozen=True)
class Catalog:
    key: str
    label: str
    source_title: str
    source_url: str
    notes: str
    entries: tuple[CatalogEntry, ...]


def _entry(key, cover, treatment, condition, a, b, c, d):
    return CatalogEntry(key, cover, treatment, condition, a, b, c, d)


# ANA, "Generacion del mapa tematico de Curva Numero (CN)", tabla 4.
# Se transcriben las 13 coberturas del modelo, sin mezclarlas con otra tabla SCS.
ANA_2015_ENTRIES = (
    _entry("ana_water", "Cuerpos de agua", "", "", 100, 100, 100, 100),
    _entry("ana_snow", "Nevados", "", "", 98, 98, 98, 98),
    _entry("ana_settlements", "Centros poblados", "", "", 77, 85, 90, 92),
    _entry("ana_crops", "Cultivos / Areas intervenidas", "", "", 62, 71, 78, 81),
    _entry("ana_open_shrub", "Matorral arbustivo abierto", "", "", 45, 66, 77, 83),
    _entry("ana_cold_grassland", "Pradera en zona de clima frio", "", "", 68, 79, 86, 89),
    _entry("ana_woody_savanna", "Sabana de arboles lenosos", "", "", 45, 66, 77, 83),
    _entry("ana_hydromorphic_savanna", "Sabana hidromorfica", "", "", 25, 55, 70, 77),
    _entry("ana_rainforest", "Selva lluviosa tropical", "", "", 25, 55, 70, 77),
    _entry("ana_bamboo_rainforest", "Selva lluviosa tropical con bambues", "", "", 25, 55, 70, 77),
    _entry("ana_seasonal_broadleaf", "Selva temporal de hojas anchas", "", "", 25, 55, 70, 77),
    _entry("ana_hydrophytic_forest", "Selva hidrofitica", "", "", 39, 61, 74, 80),
    _entry("ana_arid_desert", "Desierto en zona de clima arido", "", "", 72, 81, 88, 91),
)


# NUMCURV 1.0, pestana "Tabla General", transcrita de las capturas aportadas.
# Las abreviaturas de laboreo (R, CR, C y T) se mantienen tal como aparecen.
NUMCURV_GENERAL_ENTRIES = (
    _entry("num_fallow_bare", "Barbecho", "Desnudo", "", 77, 86, 91, 94),
    _entry("num_fallow_cr_poor", "Barbecho", "CR", "Pobre", 76, 85, 90, 93),
    _entry("num_fallow_cr_good", "Barbecho", "CR", "Buena", 74, 83, 88, 90),
    _entry("num_row_r_poor", "Cultivos alineados", "R", "Pobre", 72, 81, 88, 91),
    _entry("num_row_r_good", "Cultivos alineados", "R", "Buena", 67, 78, 85, 89),
    _entry("num_row_rcr_poor", "Cultivos alineados", "R + CR", "Pobre", 71, 80, 87, 90),
    _entry("num_row_rcr_good", "Cultivos alineados", "R + CR", "Buena", 64, 75, 82, 85),
    _entry("num_row_c_poor", "Cultivos alineados", "C", "Pobre", 70, 79, 84, 88),
    _entry("num_row_c_good", "Cultivos alineados", "C", "Buena", 65, 75, 82, 86),
    _entry("num_row_ccr_poor", "Cultivos alineados", "C + CR", "Pobre", 69, 78, 83, 87),
    _entry("num_row_ccr_good", "Cultivos alineados", "C + CR", "Buena", 64, 74, 81, 85),
    _entry("num_row_ct_poor", "Cultivos alineados", "C + T", "Pobre", 66, 74, 80, 82),
    _entry("num_row_ct_good", "Cultivos alineados", "C + T", "Buena", 62, 71, 78, 81),
    _entry("num_row_ctcr_poor", "Cultivos alineados", "C + T + CR", "Pobre", 65, 73, 79, 81),
    _entry("num_row_ctcr_good", "Cultivos alineados", "C + T + CR", "Buena", 61, 70, 77, 80),
    _entry("num_small_r_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "R", "Pobre", 65, 76, 84, 88),
    _entry("num_small_r_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "R", "Buena", 63, 75, 83, 87),
    _entry("num_small_rcr_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "R + CR", "Pobre", 64, 75, 83, 86),
    _entry("num_small_rcr_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "R + CR", "Buena", 60, 72, 80, 84),
    _entry("num_small_c_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C", "Pobre", 63, 74, 82, 85),
    _entry("num_small_c_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C", "Buena", 61, 73, 81, 84),
    _entry("num_small_ccr_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + CR", "Pobre", 62, 73, 81, 84),
    _entry("num_small_ccr_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + CR", "Buena", 60, 72, 80, 83),
    _entry("num_small_ct_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + T", "Pobre", 61, 72, 79, 82),
    _entry("num_small_ct_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + T", "Buena", 59, 70, 78, 81),
    _entry("num_small_ctcr_poor", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + T + CR", "Pobre", 60, 71, 78, 81),
    _entry("num_small_ctcr_good", "Cultivos no alineados, o con surcos pequenos o mal definidos", "C + T + CR", "Buena", 58, 69, 77, 80),
    _entry("num_legume_r_poor", "Cultivos densos de leguminosas o prados en alternancia", "R", "Pobre", 66, 77, 85, 89),
    _entry("num_legume_r_good", "Cultivos densos de leguminosas o prados en alternancia", "R", "Buena", 58, 72, 81, 85),
    _entry("num_legume_c_poor", "Cultivos densos de leguminosas o prados en alternancia", "C", "Pobre", 64, 75, 83, 85),
    _entry("num_legume_c_good", "Cultivos densos de leguminosas o prados en alternancia", "C", "Buena", 55, 69, 78, 83),
    _entry("num_legume_ct_poor", "Cultivos densos de leguminosas o prados en alternancia", "C + T", "Pobre", 63, 73, 80, 83),
    _entry("num_legume_ct_good", "Cultivos densos de leguminosas o prados en alternancia", "C + T", "Buena", 51, 67, 76, 80),
    _entry("num_natural_pasture_poor", "Pastizales o pastos naturales", "", "Pobre", 68, 79, 86, 89),
    _entry("num_natural_pasture_fair", "Pastizales o pastos naturales", "", "Regulares", 49, 69, 79, 84),
    _entry("num_natural_pasture_good", "Pastizales o pastos naturales", "", "Buenas", 39, 61, 74, 80),
    _entry("num_pasture_c_poor", "Pastizales", "C", "Pobres", 47, 67, 81, 88),
    _entry("num_pasture_c_fair", "Pastizales", "C", "Regulares", 25, 59, 75, 83),
    _entry("num_pasture_c_good", "Pastizales", "C", "Buenas", 6, 35, 70, 79),
    _entry("num_permanent_meadow", "Prados permanentes", "", "", 30, 58, 71, 78),
    _entry("num_brush_grass_poor", "Matorral-herbazal, siendo el matorral preponderante", "", "Pobres", 48, 67, 77, 83),
    _entry("num_brush_grass_fair", "Matorral-herbazal, siendo el matorral preponderante", "", "Regulares", 35, 56, 70, 77),
    _entry("num_brush_grass_good", "Matorral-herbazal, siendo el matorral preponderante", "", "Buenas", 30, 48, 65, 73),
    _entry("num_wood_grass_poor", "Combinacion de arbolado y herbazal, cultivos agricolas lenosos", "", "Pobres", 57, 73, 82, 86),
    _entry("num_wood_grass_fair", "Combinacion de arbolado y herbazal, cultivos agricolas lenosos", "", "Regulares", 43, 65, 76, 82),
    _entry("num_wood_grass_good", "Combinacion de arbolado y herbazal, cultivos agricolas lenosos", "", "Buenas", 32, 58, 72, 79),
    _entry("num_silvopasture_poor", "Montes con pastos (aprovechamientos silvopastorales)", "", "Pobres", 45, 66, 77, 83),
    _entry("num_silvopasture_fair", "Montes con pastos (aprovechamientos silvopastorales)", "", "Regulares", 36, 60, 73, 79),
    _entry("num_silvopasture_good", "Montes con pastos (aprovechamientos silvopastorales)", "", "Buenas", 25, 55, 70, 77),
    _entry("num_forest_very_poor", "Bosques", "", "I muy pobre", 56, 75, 86, 91),
    _entry("num_forest_poor", "Bosques", "", "II pobre", 46, 68, 78, 84),
    _entry("num_forest_fair", "Bosques", "", "III regular", 36, 60, 70, 76),
    _entry("num_forest_good", "Bosques", "", "IV buena", 26, 52, 63, 69),
    _entry("num_forest_very_good", "Bosques", "", "V muy buena", 15, 44, 54, 61),
    _entry("num_hamlets", "Caserios", "", "", 59, 74, 82, 86),
    _entry("num_dirt_roads", "Caminos en tierra", "", "", 72, 82, 87, 89),
    _entry("num_firm_roads", "Caminos con firme", "", "", 74, 84, 90, 92),
)


# NUMCURV 1.0, pestana "Tabla de zonas aridas", transcrita literalmente.
NUMCURV_ARID_ENTRIES = (
    _entry("arid_herb_poor", "Herbazal con algo de matorral", "", "Pobre", 70, 80, 87, 93),
    _entry("arid_herb_fair", "Herbazal con algo de matorral", "", "Medio", 60, 71, 81, 89),
    _entry("arid_herb_good", "Herbazal con algo de matorral", "", "Bueno", 50, 62, 74, 85),
    _entry("arid_oak_poor", "Oak brush, aspen, mountain mahogany, bitter brush, maple", "", "Pobre", 55, 66, 74, 79),
    _entry("arid_oak_fair", "Oak brush, aspen, mountain mahogany, bitter brush, maple", "", "Medio", 37, 48, 57, 63),
    _entry("arid_oak_good", "Oak brush, aspen, mountain mahogany, bitter brush, maple", "", "Bueno", 25, 30, 41, 48),
    _entry("arid_juniper_poor", "Pinyon, juniper, o ambos; con cubierta herbacea", "", "Pobre", 60, 75, 85, 89),
    _entry("arid_juniper_fair", "Pinyon, juniper, o ambos; con cubierta herbacea", "", "Medio", 45, 58, 73, 80),
    _entry("arid_juniper_good", "Pinyon, juniper, o ambos; con cubierta herbacea", "", "Bueno", 25, 41, 61, 71),
    _entry("arid_sage_poor", "Sagebrush con cubierta herbacea", "", "Pobre", 55, 67, 80, 85),
    _entry("arid_sage_fair", "Sagebrush con cubierta herbacea", "", "Medio", 40, 51, 63, 70),
    _entry("arid_sage_good", "Sagebrush con cubierta herbacea", "", "Bueno", 25, 35, 47, 55),
    _entry("desert_shrub_poor", "Matorral desertico: Palo verde, mesquite, cactus, bursage, saltbrush, etc.", "", "Pobre", 63, 77, 85, 88),
    _entry("desert_shrub_fair", "Matorral desertico: Palo verde, mesquite, cactus, bursage, saltbrush, etc.", "", "Medio", 55, 72, 81, 86),
    _entry("desert_shrub_good", "Matorral desertico: Palo verde, mesquite, cactus, bursage, saltbrush, etc.", "", "Bueno", 49, 68, 79, 84),
)


ANA_URL = "https://repositorio.ana.gob.pe/"
NUMCURV_URL = "https://www.hidrojing.com/recursos/"

CATALOGS = {
    "ana_scs_general": Catalog(
        "ana_scs_general",
        "ANA 2015 - Tabla 4 del modelo",
        "ANA, Generacion del mapa tematico de Curva Numero (CN), tabla 4",
        ANA_URL,
        "Transcripcion de ANA0004219.pdf. La equivalencia con la leyenda del raster debe revisarse.",
        ANA_2015_ENTRIES,
    ),
    "numcurv_general": Catalog(
        "numcurv_general",
        "NUMCURV - Tabla general",
        "NUMCURV 1.0, Tabla General",
        NUMCURV_URL,
        "Transcripcion literal de la tabla NUMCURV aportada por el usuario; R, CR, C y T se conservan como en la fuente.",
        NUMCURV_GENERAL_ENTRIES,
    ),
    "numcurv_arid": Catalog(
        "numcurv_arid",
        "NUMCURV - Tabla de zonas aridas",
        "NUMCURV 1.0, Tabla de zonas aridas",
        NUMCURV_URL,
        "Transcripcion literal de la tabla NUMCURV aportada por el usuario, incluidos los valores del grupo A.",
        NUMCURV_ARID_ENTRIES,
    ),
}


def get_catalog(key):
    try:
        return CATALOGS[str(key)]
    except KeyError as error:
        raise ValueError(f"Catalogo CN desconocido: {key!r}.") from error


def write_full_catalog(path, catalog_key):
    """Exporta un catalogo de consulta, sin fingir codigos de un raster LULC."""

    catalog = get_catalog(catalog_key)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    headers = (
        "CatalogEntryID", "Cover", "Treatment", "HydrologicCondition",
        "A", "B", "C", "D", "CatalogID", "CatalogSource", "SourceURL",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        for entry in catalog.entries:
            writer.writerow(
                [
                    entry.key, entry.cover, entry.treatment, entry.condition,
                    entry.a if entry.a is not None else "",
                    entry.b if entry.b is not None else "",
                    entry.c if entry.c is not None else "",
                    entry.d if entry.d is not None else "",
                    catalog.key, catalog.source_title, catalog.source_url,
                ]
            )
    return str(output)


def write_catalog_lookup(path, catalog_key, assignments):
    """Escribe una tabla compatible con HidroCN/HEC-GeoHMS con trazabilidad."""

    catalog = get_catalog(catalog_key)
    entries = {entry.key: entry for entry in catalog.entries}
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    rows = []
    for assignment in assignments:
        lu_value = int(assignment["lu_value"])
        if lu_value in seen:
            raise ValueError(f"LUValue duplicado: {lu_value}.")
        seen.add(lu_value)
        entry_key = str(assignment.get("entry_key") or "")
        if entry_key not in entries:
            raise ValueError(f"Seleccione una categoria para LUValue {lu_value}.")
        entry = entries[entry_key]
        description = str(assignment.get("description") or entry.cover).strip()
        values = {}
        for group, default in entry.values.items():
            raw = assignment[group] if group in assignment else default
            if raw is None or not str(raw).strip():
                values[group] = ""
                continue
            number = float(raw)
            if not 0.0 < number <= 100.0:
                raise ValueError(f"CN-{group} para LUValue {lu_value} debe estar en (0, 100].")
            values[group] = int(number) if number.is_integer() else number
        rows.append(
            [
                lu_value,
                description,
                values["A"],
                values["B"],
                values["C"],
                values["D"],
                catalog.key,
                catalog.source_title,
                catalog.source_url,
                entry.cover,
                entry.treatment,
                entry.condition,
            ]
        )
    if not rows:
        raise ValueError("No existen asignaciones para guardar.")
    headers = (
        "LUValue", "Description", "A", "B", "C", "D", "CatalogID",
        "CatalogSource", "SourceURL", "Cover", "Treatment", "HydrologicCondition",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    return str(output)
