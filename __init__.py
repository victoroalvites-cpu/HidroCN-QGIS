"""Punto de entrada de HidroCN para QGIS."""


def classFactory(iface):
    from .plugin import HidroCnPlugin

    return HidroCnPlugin(iface)
