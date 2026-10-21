# Historial de cambios de HidroCN

## 0.5.3 - 2026-10-21

- La descarga GEE lee y escribe bloques mediante GDAL RasterIO para evitar
  el fallo intermitente `numpy.core.multiarray failed to import` de
  `ReadAsArray`/`WriteArray` en el entorno de QGIS.
- El resumen por subcuenca usa la misma lectura robusta.
- Conserva en el mensaje de error los detalles del proceso externo cuando
  sean necesarios para diagnosticar fallos posteriores.

## 0.5.2 - 2026-10-21

- Evita que los avisos del proceso de Earth Engine llenen los canales de
  salida y detengan la descarga: se escriben en archivos temporales.
- Elimina la segunda lectura `ComputeStatistics` de GDAL; la media, el minimo,
  el maximo y la cobertura ya se calculan en la primera lectura del GeoTIFF.
- Muestra pasos internos de la normalizacion para localizar una espera real.

## 0.5.1 - 2026-10-21

- Estadisticos globales calculados sobre el GeoTIFF final, sin reducciones
  adicionales en Earth Engine despues de la descarga.
- CSV, GeoPackage y metadatos se guardan al completar cada condicion; los
  metadatos indican `partial` o `complete`.
- Descarga en archivo temporal hasta terminar la normalizacion NoData.
- Progreso por etapas y tiempos en el registro, con cancelacion sin dialogo de
  error para los productos ya completados.
- Interfaz renovada con temas Sistema, Claro y Oscuro, recordados por QGIS.

## 0.5.0 - 2026-09-14

- Primera version publica estable.
- Descarga de CN Peru y GCN250 desde Google Earth Engine, con soporte para un
  asset personalizado.
- Construccion local tipo HEC-GeoHMS mediante raster LULC, raster HSG y tabla
  CN por grupos A-D.
- Condiciones CN-I, CN-II y CN-III; CN-I y CN-III se derivan de CN-II con las
  relaciones publicadas por ANA.
- Biblioteca trazable de tablas ANA 2015 y NUMCURV general/zonas aridas.
- GeoTIFF proyectados, NoData real, simbologia basada en el rango valido,
  metadatos JSON y estadisticas areales por subunidad en CSV y GeoPackage.
- Manual tecnico y de usuario actualizado, icono propio y metadatos publicos.

## 0.4.1 - 2026-09-14

- Ajuste de las conversiones CN-II a CN-I y CN-III a las relaciones ANA.

## 0.4.0 - 2026-09-14

- Nuevo icono y estadisticas por subunidad para resultados descargados de GEE.

## 0.3.1 - 2026-09-14

- Biblioteca ANA/NUMCURV y asistente de correspondencia LULC.

## 0.2.0 - 2026-09-13

- Flujo local tipo HEC-GeoHMS, control de calidad y productos trazables.
