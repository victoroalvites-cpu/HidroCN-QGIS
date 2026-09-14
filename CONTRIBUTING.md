# Contribuir a HidroCN

Gracias por ayudar a mejorar HidroCN. Antes de proponer cambios, abra una
incidencia en https://github.com/victoroalvites-cpu/HidroCN-QGIS/issues con:

- version de QGIS y sistema operativo;
- fuente CN o ruta de calculo utilizada;
- SRC, resolucion y tipo de cuenca/subcuencas;
- mensaje completo del registro de HidroCN;
- datos minimos reproducibles que puedan compartirse legalmente.

Para validar cambios desde la carpeta que contiene el complemento:

```text
python -m unittest discover -s hidro_cn_qgis/tests -v
```

Los cambios deben conservar NoData fuera de la cuenca, la trazabilidad de las
fuentes y la compatibilidad con QGIS 3.28 o superior. No incluya credenciales,
tokens, datos personales ni archivos cuya licencia impida su redistribucion.
