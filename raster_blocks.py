"""Lectura de bloques GDAL sin cargar la extension opcional osgeo.gdal_array."""


def read_float64_block(band, x_offset, y_offset, width, height, np, gdal):
    raw = band.ReadRaster(
        x_offset, y_offset, width, height,
        buf_xsize=width, buf_ysize=height, buf_type=gdal.GDT_Float64,
    )
    expected = width * height * 8
    if raw is None or len(raw) != expected:
        raise RuntimeError("GDAL no pudo leer un bloque completo del raster.")
    return np.frombuffer(raw, dtype=np.float64).reshape(height, width).copy()


def write_float64_block(band, x_offset, y_offset, values, gdal):
    height, width = values.shape
    result = band.WriteRaster(
        x_offset, y_offset, width, height,
        values.tobytes(order="C"),
        buf_xsize=width, buf_ysize=height, buf_type=gdal.GDT_Float64,
    )
    if result not in (None, 0):
        raise RuntimeError("GDAL no pudo escribir un bloque completo del raster.")
