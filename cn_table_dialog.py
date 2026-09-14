"""Asistente para relacionar clases LULC con catalogos CN-II trazables."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .core.cn_catalog import (
    CATALOGS,
    get_catalog,
    write_catalog_lookup,
    write_full_catalog,
)


class CnTableBuilderDialog(QDialog):
    """Construye una tabla HEC-GeoHMS a partir de los codigos de un raster."""

    def __init__(self, lulc_codes, default_folder, parent=None):
        super().__init__(parent)
        self.codes = list(lulc_codes)
        self.default_folder = str(default_folder)
        self.output_path = ""
        self.setWindowTitle("HidroCN - Biblioteca ANA / NumCurv")
        self.resize(1120, 640)
        self._build_ui()
        self._load_catalog()

    def _build_ui(self):
        root = QVBoxLayout(self)
        intro = QLabel(
            "Asigne a cada codigo del raster una cobertura, tratamiento y condicion. "
            "HidroCN copia los CN-II A-D del catalogo; puede revisarlos o editarlos antes de guardar."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Catalogo"))
        self.catalog_combo = QComboBox()
        for key, catalog in CATALOGS.items():
            self.catalog_combo.addItem(catalog.label, key)
        source_row.addWidget(self.catalog_combo, 1)
        self.export_catalog_button = QPushButton("Exportar catalogo completo")
        source_row.addWidget(self.export_catalog_button)
        root.addLayout(source_row)

        self.source_note = QLabel()
        self.source_note.setWordWrap(True)
        self.source_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.source_note)

        self.table = QTableWidget(len(self.codes), 7)
        self.table.setHorizontalHeaderLabels(
            ["LUValue", "Descripcion de salida", "Categoria del catalogo", "A", "B", "C", "D"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for column in range(3, 7):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("Guardar tabla CN-II")
        root.addWidget(self.buttons)

        self.catalog_combo.currentIndexChanged.connect(self._load_catalog)
        self.export_catalog_button.clicked.connect(self._export_full_catalog)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

    @staticmethod
    def _locked_item(text):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _load_catalog(self, *_args):
        catalog = get_catalog(self.catalog_combo.currentData())
        self.source_note.setText(
            f"Fuente: {catalog.source_title}\n{catalog.source_url}\n{catalog.notes}"
        )
        self.table.setRowCount(len(self.codes))
        for row, code in enumerate(self.codes):
            self.table.setItem(row, 0, self._locked_item(code))
            self.table.setItem(row, 1, QTableWidgetItem(""))
            combo = QComboBox()
            combo.addItem("Seleccione una categoria...", "")
            for entry in catalog.entries:
                combo.addItem(entry.label, entry.key)
            combo.currentIndexChanged.connect(
                lambda _index, current_row=row: self._category_changed(current_row)
            )
            self.table.setCellWidget(row, 2, combo)
            for column in range(3, 7):
                self.table.setItem(row, column, QTableWidgetItem(""))

    def _category_changed(self, row):
        combo = self.table.cellWidget(row, 2)
        entry_key = str(combo.currentData() or "")
        if not entry_key:
            return
        catalog = get_catalog(self.catalog_combo.currentData())
        entry = next(item for item in catalog.entries if item.key == entry_key)
        description = self.table.item(row, 1)
        if description is not None and not description.text().strip():
            description.setText(entry.label)
        for column, group in enumerate(("A", "B", "C", "D"), start=3):
            value = entry.values[group]
            self.table.item(row, column).setText("" if value is None else str(value))

    def _assignments(self):
        assignments = []
        missing = []
        for row, code in enumerate(self.codes):
            combo = self.table.cellWidget(row, 2)
            entry_key = str(combo.currentData() or "")
            if not entry_key:
                missing.append(str(code))
                continue
            item = self.table.item(row, 1)
            assignment = {
                "lu_value": code,
                "description": item.text().strip() if item else "",
                "entry_key": entry_key,
            }
            for column, group in enumerate(("A", "B", "C", "D"), start=3):
                value_item = self.table.item(row, column)
                assignment[group] = value_item.text().strip() if value_item else ""
            assignments.append(assignment)
        if missing:
            raise ValueError("Falta seleccionar una categoria para LUValue: " + ", ".join(missing))
        return assignments

    def _save(self):
        try:
            assignments = self._assignments()
        except Exception as error:
            QMessageBox.warning(self, "Tabla CN-II", str(error))
            return
        default_path = str(Path(self.default_folder) / "tabla_CN_HidroCN_catalogo.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar tabla CN-II", default_path, "Tabla CSV (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.output_path = write_catalog_lookup(
                path, str(self.catalog_combo.currentData()), assignments
            )
        except Exception as error:
            QMessageBox.warning(self, "Tabla CN-II", str(error))
            return
        self.accept()

    def _export_full_catalog(self):
        catalog = get_catalog(self.catalog_combo.currentData())
        default_path = str(Path(self.default_folder) / f"catalogo_{catalog.key}.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar catalogo CN-II", default_path, "Tabla CSV (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            write_full_catalog(path, catalog.key)
        except Exception as error:
            QMessageBox.warning(self, "Catalogo CN-II", str(error))
            return
        QMessageBox.information(self, "Catalogo CN-II", "Catalogo exportado:\n" + path)
