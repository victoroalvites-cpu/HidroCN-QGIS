# HidroCN - Curva Numero

Complemento QGIS para obtener mapas SCS-CN recortados por una cuenca y calcular
estadisticas por subcuenca. Incluye dos rutas independientes:

1. descarga desde Google Earth Engine (CN Peru, GCN250 o asset personalizado);
2. construccion local tipo HEC-GeoHMS mediante uso del suelo, grupo hidrologico
   del suelo y una tabla CN-II.

## Version 0.5.3

- Compatible con QGIS 3.28 a 3.99.
- Estadisticos calculados localmente desde el GeoTIFF final. El progreso indica
  la etapa interna y el tiempo transcurrido, sin repetir la lectura GDAL.
- La ruta GEE procesa los bloques sin `osgeo.gdal_array`, para evitar el fallo
  intermitente de importacion `numpy.core.multiarray` observado en CN-I.
- Selector de apariencia Sistema, Claro u Oscuro en la cabecera.
- Metadatos publicos, manual tecnico y de usuario, licencia y canal de incidencias.
- Conserva las funciones validadas en 0.4.1: descarga desde GEE, calculo local
  tipo HEC-GeoHMS, catalogos ANA/NUMCURV y estadisticas por subunidad.

Repositorio y soporte:

- Codigo fuente: https://github.com/victoroalvites-cpu/HidroCN-QGIS
- Incidencias: https://github.com/victoroalvites-cpu/HidroCN-QGIS/issues

## Cambios de la version 0.4.1

- CN-I se deriva como `4.2 * CN-II / (10 - 0.058 * CN-II)`.
- CN-III se deriva como `23 * CN-II / (10 + 0.13 * CN-II)`.
- Ambas expresiones corresponden a las relaciones (1) y (2) de ANA0004219.

## Cambios de la version 0.4.0

- Nuevo icono propio de HidroCN para la barra de herramientas de QGIS.
- Los nombres visibles de los catalogos ya no incluyen el sufijo `(CN-II)`.
- Las descargas GEE generan tambien un GeoPackage y un CSV con media, minimo,
  maximo y cobertura de cada condicion CN por subunidad seleccionada.

## Cambios de la version 0.3.1

- Boton `Biblioteca ANA / NumCurv` dentro del calculo local.
- Deteccion de todos los codigos enteros presentes en el raster LULC.
- Catalogo ANA con los 13 valores exactos de la tabla 4 de ANA0004219.
- Tablas NUMCURV General y de zonas aridas transcritas de la aplicacion,
  incluidos los valores del grupo hidrologico A.
- Asistente para relacionar cada codigo LULC con cobertura, tratamiento y
  condicion hidrologica, con revision editable de los valores A-D.
- Exportacion de la tabla completa o de una tabla lista para el calculo, con
  fuente y URL conservadas en columnas adicionales de trazabilidad.
- Los valores no publicados para un grupo se mantienen vacios. Esas
  combinaciones se reportan como NoData en vez de inventar una asignacion.

## Funciones incorporadas en la version 0.2.0

- Nueva pestana `Calculo local HEC-GeoHMS` que no necesita Earth Engine.
- Entradas raster de uso/cobertura del suelo (LULC) y grupo hidrologico (HSG).
- HSG codificado como `1=A`, `2=B`, `3=C`, `4=D`.
- Tabla compatible con HEC-GeoHMS: `LUValue,Description,A,B,C,D`.
- Compatibilidad adicional con tablas de SCS-CN Builder:
  `LULC_code,CN_A,CN_B,CN_C,CN_D`.
- Reproyeccion, recorte y alineacion exacta de LULC/HSG a una malla comun en el
  SRC proyectado y resolucion elegidos.
- Cruce celda a celda para CN-II y derivacion opcional de CN-I y CN-III.
- Deteccion de codigos de uso del suelo ausentes, valores HSG fuera de 1..4 y
  pixeles validos sin correspondencia.
- GeoPackage y CSV con media, minimo, maximo y cobertura CN por subcuenca.
- Informe HTML, metadatos JSON y raster alineados para auditoria.
- Simbologia QGIS basada en el minimo y maximo real; NoData es `-9999`.

## Flujo local tipo HEC-GeoHMS

1. Cargue en QGIS una capa poligonal de cuencas o subcuencas.
2. Cargue un raster LULC con codigos enteros y un raster HSG con valores 1..4.
3. Seleccione la capa de cuenca y decida si se procesan solo los elementos
   seleccionados.
4. Abra la pestana `Calculo local HEC-GeoHMS`.
5. Seleccione LULC, HSG y un campo identificador unico de subcuenca.
6. Seleccione una tabla CSV, genere una vacia con `Crear plantilla` o pulse
   `Biblioteca ANA / NumCurv`. El asistente detecta los codigos del raster y
   exige relacionar cada uno con una categoria hidrologica antes de guardar.
7. Elija CN-I, CN-II y/o CN-III.
8. Defina un SRC proyectado y una resolucion. El boton de UTM usa el centroide
   de la cuenca para sugerir el huso.
9. Seleccione la carpeta y el prefijo, y pulse `Construir CN local`.
10. Revise el registro y el informe HTML. Una combinacion no definida se escribe
    como NoData, nunca se sustituye silenciosamente.

La media por subcuenca se calcula sobre las celdas validas cuyo centro cae en
el poligono. El GeoPackage de salida contiene el identificador y los campos
`CN_I_MEAN`, `CN_II_MEAN`, `CN_III_MEAN` (segun productos seleccionados), junto
con minimo, maximo y porcentaje de cobertura.

## Flujo desde Google Earth Engine

1. Seleccione la cuenca o los poligonos de interes.
2. Ingrese el proyecto Google Cloud habilitado para Earth Engine.
3. Pulse `Conectar / autorizar` y complete personalmente el acceso en el
   navegador.
4. Seleccione CN Peru, GCN250 o un asset personalizado.
5. Seleccione las condiciones y un SRC proyectado.
6. Defina resolucion, carpeta y prefijo; pulse `Descargar CN`.

La geometria se envia temporalmente a GEE en WGS 84 y no se registra como
asset. Los GeoTIFF se descargan en el SRC proyectado elegido y se normalizan con
NoData real fuera de la cuenca.
El CSV, el GeoPackage y los metadatos se actualizan despues de cada condicion
completada. Si se cancela, solo los productos terminados se conservan como
salidas finales; los metadatos indican `partial` hasta terminar todas las
condiciones.
La cobertura global se calcula como pixeles CN validos divididos por los
pixeles de la cuenca en la malla final. El area de cuenca en km2 se calcula
con la geometria proyectada al SRC de salida.

## Dependencias

El calculo local usa NumPy y GDAL/OGR ya incluidos en QGIS. La ruta GEE requiere
`earthengine-api` en el Python de QGIS. El cuadro `Como instalar la API` genera
el comando correcto para PowerShell, incluyendo `&` delante de la ruta entre
comillas. Reinicie QGIS despues de instalarla.

HidroCN no solicita, lee ni almacena contrasenas. La autorizacion de Earth
Engine se completa personalmente en el navegador del usuario.

## Criterios tecnicos y referencias

El diseno local sigue el contrato de tabla y la secuencia conceptual de
HEC-GeoHMS/HEC-HMS: alinear LULC y HSG, asignar CN por cada combinacion y resumir
el grid por subcuenca. SCS-CN Builder (Nikola V. Djokic, GPL-3.0-or-later) se uso
como referencia funcional para la alineacion, los controles de calidad y los
productos de salida. La implementacion de HidroCN se integro de forma propia en
su arquitectura, con soporte adicional para CN-I y el esquema HEC-GeoHMS.

- HEC-HMS: Creating a Curve Number Grid and Computing Subbasin Average Curve
  Number Values.
- HEC-GeoHMS User's Manual 10.1, seccion de generacion del CN Grid.
- SCS-CN Builder: https://github.com/nikolavdjokic995-ctrl/SCS-CN-Builder
- ANA, `Generacion del mapa tematico de Curva Numero (CN)`, tabla 4 del
  archivo `ANA0004219.pdf`.
- NUMCURV 1.0, pestanas `Tabla General` y `Tabla de zonas aridas`.
- USDA NRCS, National Engineering Handbook 630, capitulo 9:
  https://directives.nrcs.usda.gov/sites/default/files2/1712930607/7306.pdf

Los valores CN dependen de la clasificacion LULC, el tratamiento y la condicion
hidrologica. Los catalogos son referencias seleccionables, no una equivalencia
automatica ni universal con cualquier producto de cobertura.

## Limitaciones conocidas

- La ruta local acepta raster LULC y HSG guardados en disco. Las capas
  vectoriales deben rasterizarse previamente con sus campos de codigo.
- La malla usa la extension ajustada a la cuenca, la resolucion elegida y un
  origen alineado a multiplos de esa resolucion; todavia no copia el origen de
  celda de un DEM de referencia.
- Si hay subcuencas solapadas, la ultima geometria rasterizada prevalece en la
  zona solapada. Deben corregirse los solapes antes del calculo.
- La descarga GEE directa sigue sujeta a limites de tamano; el mosaico por
  teselas queda para una version posterior.
- No convierte directamente GeoTIFF a HEC-DSS.

## Pruebas

Pruebas puras desde la carpeta que contiene `hidro_cn_qgis`:

```text
python -m unittest discover -s hidro_cn_qgis/tests -v
```

La prueba `tests/qgis_smoke.py` se ejecuta con el Python real de QGIS y valida
la carga del dialogo, NoData, rampa dinamica y un flujo local sintetico completo.

## Licencia

GNU GPL v3 o posterior.

## English summary

HidroCN is a QGIS plugin that downloads SCS Curve Number rasters from Google
Earth Engine or builds them locally from a land-use raster, a hydrologic soil
group raster and a HEC-GeoHMS-compatible lookup table. It creates CN-I, CN-II
and CN-III products, projected GeoTIFF files, auditable metadata and zonal
statistics for each watershed or subbasin.

The local workflow uses libraries bundled with QGIS. The optional GEE workflow
requires `earthengine-api`, an Earth Engine-enabled Google Cloud project and
interactive authorization performed by the user. The CN Peru source is regional
to Peru; GCN250 and custom assets can be used elsewhere subject to their source
coverage and licensing.
