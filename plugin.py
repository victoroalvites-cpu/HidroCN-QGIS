"""Integracion de HidroCN con la interfaz principal de QGIS."""

from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dialog import HidroCnDialog


class HidroCnPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.menu_name = self.tr("&HidroCN")

    def tr(self, text):
        return QCoreApplication.translate("HidroCnPlugin", text)

    def initGui(self):
        self.action = QAction(
            QIcon(str(Path(__file__).with_name("icon.png"))),
            self.tr("HidroCN - Curva Numero"),
            self.iface.mainWindow(),
        )
        self.action.setObjectName("hidroCnCurveNumberAction")
        self.action.setToolTip(self.tr("Descargar y preparar mapas de numero de curva SCS"))
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu_name, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            self.dialog = HidroCnDialog(self.iface, self.iface.mainWindow())
        self.dialog.refresh_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
