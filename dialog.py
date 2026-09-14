"""Interfaz principal de HidroCN."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QApplication,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsApplication,
    QgsColorRampShader,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsTask,
    QgsVectorLayer,
)
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionWidget

from .core.spatial_reference import suggested_utm_authid
from .gee_service import (
    GeeError,
    SOURCE_CATALOG,
    authenticate_ee_external,
    dependency_status,
    run_gee_external,
)
from .local_cn_service import (
    LocalCnError,
    run_local_cn_workflow,
    unique_integer_raster_values,
)
from .core.local_cn import write_lookup_template
from .cn_table_dialog import CnTableBuilderDialog


class HidroCnDialog(QDialog):
    SETTINGS_PREFIX = "HidroCN"

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._busy = 0
        self._current_task = None
        self._dependency_available = False
        self.setWindowTitle("HidroCN - Curva Numero")
        self.resize(780, 720)
        self._build_ui()
        self._restore_settings()
        self.refresh_layers()
        self._update_dependency_status()

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            "Genera mapas SCS-CN para una cuenca de QGIS: descargados desde Google Earth "
            "Engine o calculados localmente mediante uso del suelo, grupo hidrologico y una "
            "tabla compatible con HEC-GeoHMS."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        basin_group = QGroupBox("1. Cuenca en estudio")
        basin_form = QFormLayout(basin_group)
        self.basin_combo = QgsMapLayerComboBox()
        self.basin_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.local_id_combo = QComboBox()
        self.selected_only_check = QCheckBox("Procesar solo los elementos seleccionados")
        self.selected_only_check.setChecked(True)
        basin_buttons = QHBoxLayout()
        self.active_layer_button = QPushButton("Usar capa activa")
        self.validate_button = QPushButton("Validar cuenca")
        basin_buttons.addWidget(self.active_layer_button)
        basin_buttons.addWidget(self.validate_button)
        basin_buttons.addStretch(1)
        basin_form.addRow("Capa poligonal", self.basin_combo)
        basin_form.addRow("Identificador de subunidad", self.local_id_combo)
        basin_form.addRow("", self.selected_only_check)
        basin_form.addRow("", basin_buttons)
        root.addWidget(basin_group)

        self.method_tabs = QTabWidget()
        gee_tab = QWidget()
        gee_layout = QVBoxLayout(gee_tab)

        gee_group = QGroupBox("2. Google Earth Engine")
        gee_form = QFormLayout(gee_group)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Ejemplo: ee-mi-proyecto")
        connection_buttons = QHBoxLayout()
        self.connect_button = QPushButton("Conectar / autorizar")
        self.reauthorize_button = QPushButton("Cambiar autorizacion")
        self.check_button = QPushButton("Comprobar conexion")
        self.install_help_button = QPushButton("Como instalar la API")
        connection_buttons.addWidget(self.connect_button)
        connection_buttons.addWidget(self.reauthorize_button)
        connection_buttons.addWidget(self.check_button)
        connection_buttons.addWidget(self.install_help_button)
        self.connection_status = QLabel("Comprobando earthengine-api...")
        self.connection_status.setWordWrap(True)
        gee_form.addRow("Proyecto Google Cloud", self.project_edit)
        gee_form.addRow("", connection_buttons)
        gee_form.addRow("Estado", self.connection_status)
        gee_layout.addWidget(gee_group)

        source_group = QGroupBox("3. Fuente y condiciones antecedentes")
        source_form = QFormLayout(source_group)
        self.source_combo = QComboBox()
        for key, definition in SOURCE_CATALOG.items():
            self.source_combo.addItem(definition.label, key)
        self.source_combo.addItem("Asset personalizado (interpretado como CN-II)", "custom")
        self.custom_asset_edit = QLineEdit()
        self.custom_asset_edit.setPlaceholderText("projects/.../assets/... o users/...")
        self.custom_band_edit = QLineEdit()
        self.custom_band_edit.setPlaceholderText("Vacio = primera banda")
        condition_row = QHBoxLayout()
        self.dry_check = QCheckBox("CN-I seco")
        self.normal_check = QCheckBox("CN-II normal")
        self.wet_check = QCheckBox("CN-III humedo")
        self.dry_check.setChecked(True)
        self.normal_check.setChecked(True)
        self.wet_check.setChecked(True)
        condition_row.addWidget(self.dry_check)
        condition_row.addWidget(self.normal_check)
        condition_row.addWidget(self.wet_check)
        condition_row.addStretch(1)
        self.inspect_button = QPushButton("Inspeccionar fuente")
        self.source_note = QLabel()
        self.source_note.setWordWrap(True)
        source_form.addRow("Fuente", self.source_combo)
        source_form.addRow("Asset personalizado", self.custom_asset_edit)
        source_form.addRow("Banda", self.custom_band_edit)
        source_form.addRow("Productos", condition_row)
        source_form.addRow("", self.inspect_button)
        source_form.addRow("Trazabilidad", self.source_note)
        gee_layout.addWidget(source_group)
        gee_outputs = QLabel(
            "Salidas: raster CN; GeoPackage y CSV con media, minimo, maximo y cobertura "
            "por subunidad; metadatos JSON."
        )
        gee_outputs.setWordWrap(True)
        gee_layout.addWidget(gee_outputs)
        gee_layout.addStretch(1)
        self.method_tabs.addTab(gee_tab, "Desde GEE")

        local_tab = QWidget()
        local_layout = QVBoxLayout(local_tab)
        local_intro = QLabel(
            "Flujo tipo HEC-GeoHMS: ambos raster se reproyectan, recortan y alinean a la "
            "misma malla. HSG debe usar 1=A, 2=B, 3=C y 4=D. Las combinaciones sin fila "
            "en la tabla se guardan como NoData y se informan en el control de calidad."
        )
        local_intro.setWordWrap(True)
        local_layout.addWidget(local_intro)
        local_inputs = QGroupBox("Datos para construir el grid CN")
        local_form = QFormLayout(local_inputs)
        self.local_lulc_combo = QgsMapLayerComboBox()
        self.local_lulc_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.local_hsg_combo = QgsMapLayerComboBox()
        self.local_hsg_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.local_lookup_edit = QLineEdit()
        self.local_lookup_edit.setPlaceholderText("CSV: LUValue,Description,A,B,C,D")
        self.local_lookup_button = QPushButton("Examinar")
        self.local_template_button = QPushButton("Crear plantilla")
        self.local_catalog_button = QPushButton("Biblioteca ANA / NumCurv")
        lookup_row = QHBoxLayout()
        lookup_row.addWidget(self.local_lookup_edit, 1)
        lookup_row.addWidget(self.local_lookup_button)
        lookup_row.addWidget(self.local_template_button)
        lookup_row.addWidget(self.local_catalog_button)
        local_form.addRow("Raster de uso del suelo", self.local_lulc_combo)
        local_form.addRow("Raster de grupo HSG", self.local_hsg_combo)
        local_form.addRow("Tabla CN-II", lookup_row)
        local_condition_row = QHBoxLayout()
        self.local_dry_check = QCheckBox("CN-I seco")
        self.local_normal_check = QCheckBox("CN-II normal")
        self.local_wet_check = QCheckBox("CN-III humedo")
        for check in (self.local_dry_check, self.local_normal_check, self.local_wet_check):
            check.setChecked(True)
            local_condition_row.addWidget(check)
        local_condition_row.addStretch(1)
        local_form.addRow("Productos", local_condition_row)
        local_layout.addWidget(local_inputs)
        local_outputs = QLabel(
            "Salidas: CN-I, CN-II y/o CN-III; raster LULC/HSG alineados; GeoPackage y CSV "
            "con media, minimo, maximo y cobertura por subcuenca; informe HTML y metadatos JSON."
        )
        local_outputs.setWordWrap(True)
        local_layout.addWidget(local_outputs)
        local_layout.addStretch(1)
        self.method_tabs.addTab(local_tab, "Calculo local HEC-GeoHMS")
        root.addWidget(self.method_tabs)

        output_group = QGroupBox("4. Salida proyectada")
        output_form = QFormLayout(output_group)
        self.crs_widget = QgsProjectionSelectionWidget()
        project_crs = QgsProject.instance().crs()
        if project_crs.isValid():
            self.crs_widget.setCrs(project_crs)
        self.suggest_utm_button = QPushButton("Sugerir UTM desde la cuenca")
        crs_row = QHBoxLayout()
        crs_row.addWidget(self.crs_widget, 1)
        crs_row.addWidget(self.suggest_utm_button)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setDecimals(2)
        self.scale_spin.setRange(1.0, 100000.0)
        self.scale_spin.setValue(90.0)
        self.scale_spin.setSuffix(" m")
        self.scale_note = QLabel(
            "Se usa vecino mas cercano para conservar las clases y los valores CN."
        )
        self.scale_note.setWordWrap(True)
        self.output_folder_edit = QLineEdit()
        self.output_folder_button = QPushButton("Examinar")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.output_folder_edit, 1)
        folder_row.addWidget(self.output_folder_button)
        self.prefix_edit = QLineEdit("hidrocn")
        self.add_results_check = QCheckBox("Agregar los resultados al proyecto QGIS")
        self.add_results_check.setChecked(True)
        output_form.addRow("SRC del GeoTIFF", crs_row)
        output_form.addRow("Resolucion", self.scale_spin)
        output_form.addRow("", self.scale_note)
        output_form.addRow("Carpeta", folder_row)
        output_form.addRow("Prefijo", self.prefix_edit)
        output_form.addRow("", self.add_results_check)
        root.addWidget(output_group)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(130)
        root.addWidget(QLabel("Registro"))
        root.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar operacion")
        self.cancel_button.setEnabled(False)
        self.download_button = QPushButton("Descargar CN")
        self.local_calculate_button = QPushButton("Construir CN local")
        self.close_button = QPushButton("Cerrar")
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.local_calculate_button)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)

        self.active_layer_button.clicked.connect(self._use_active_layer)
        self.validate_button.clicked.connect(self._validate_basin_clicked)
        self.connect_button.clicked.connect(lambda: self._connect(False))
        self.reauthorize_button.clicked.connect(lambda: self._connect(True))
        self.check_button.clicked.connect(self._check_connection)
        self.install_help_button.clicked.connect(self._show_install_help)
        self.inspect_button.clicked.connect(self._inspect_source)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.suggest_utm_button.clicked.connect(self._suggest_utm)
        self.output_folder_button.clicked.connect(self._choose_output_folder)
        self.download_button.clicked.connect(self._download)
        self.local_calculate_button.clicked.connect(self._calculate_local)
        self.local_lookup_button.clicked.connect(self._choose_lookup_csv)
        self.local_template_button.clicked.connect(self._create_lookup_template)
        self.local_catalog_button.clicked.connect(self._open_lookup_catalog)
        self.basin_combo.layerChanged.connect(self._update_id_fields)
        self.cancel_button.clicked.connect(self._cancel_current_task)
        self.close_button.clicked.connect(self.close)
        self._source_changed()
        self._update_id_fields()

    def refresh_layers(self):
        self.basin_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        current = self.basin_combo.currentLayer()
        if current is not None:
            return
        candidates = []
        for layer in QgsProject.instance().mapLayers().values():
            name = layer.name().lower()
            if "cuenca" in name or "watershed" in name:
                candidates.append(layer)
        if candidates:
            candidates.sort(key=lambda layer: ("sub" in layer.name().lower(), len(layer.name())))
            self.basin_combo.setLayer(candidates[0])

    def _restore_settings(self):
        settings = QSettings()
        self.project_edit.setText(settings.value(f"{self.SETTINGS_PREFIX}/project_id", "", str))
        default_root = QgsProject.instance().homePath() or str(Path.home())
        default_output = str(Path(default_root) / "07_CN")
        self.output_folder_edit.setText(
            settings.value(f"{self.SETTINGS_PREFIX}/output_folder", default_output, str)
        )

    def _save_settings(self):
        settings = QSettings()
        settings.setValue(f"{self.SETTINGS_PREFIX}/project_id", self.project_edit.text().strip())
        settings.setValue(f"{self.SETTINGS_PREFIX}/output_folder", self.output_folder_edit.text().strip())

    def _update_dependency_status(self):
        status = dependency_status()
        self._dependency_available = bool(status.get("available"))
        if self._dependency_available:
            self.connection_status.setText(
                f"earthengine-api disponible, version {status.get('version', 'desconocida')}."
            )
        else:
            self.connection_status.setText(str(status.get("error", "earthengine-api no disponible.")))
        self._set_controls_enabled()

    def _show_install_help(self):
        python_executable = Path(sys.prefix) / ("python.exe" if os.name == "nt" else "bin/python")
        if os.name == "nt":
            command = f'& "{python_executable}" -m pip install --user earthengine-api'
        else:
            command = f'"{python_executable}" -m pip install --user earthengine-api'
        message = QMessageBox(self)
        message.setWindowTitle("Instalar earthengine-api")
        message.setIcon(QMessageBox.Information)
        message.setText(
            "Ejecute este comando fuera de QGIS y despues reinicie la aplicacion:\n\n" + command
        )
        copy_button = message.addButton("Copiar comando", QMessageBox.ActionRole)
        message.addButton("Cerrar", QMessageBox.RejectRole)
        message.exec()
        if message.clickedButton() is copy_button:
            QApplication.clipboard().setText(command)

    def _set_controls_enabled(self):
        enabled = self._busy == 0 and self._dependency_available
        for button in (
            self.connect_button,
            self.reauthorize_button,
            self.check_button,
            self.inspect_button,
            self.download_button,
        ):
            button.setEnabled(enabled)
        self.local_calculate_button.setEnabled(self._busy == 0)
        self.local_template_button.setEnabled(self._busy == 0)
        self.local_catalog_button.setEnabled(self._busy == 0)
        self.cancel_button.setEnabled(self._busy > 0)

    def _set_busy(self, busy):
        self._busy += 1 if busy else -1
        self._busy = max(0, self._busy)
        self._set_controls_enabled()

    def _append_log(self, text):
        self.log.appendPlainText(str(text))

    def _task(self, description, function, finished):
        self._set_busy(True)
        self._append_log(description + "...")

        def worker(task):
            if task.isCanceled():
                return None
            return function(task)

        def completed(exception, result=None):
            self._set_busy(False)
            self._current_task = None
            if exception is not None:
                self._append_log("ERROR: " + str(exception))
                QMessageBox.critical(self, "HidroCN", str(exception))
                return
            if result is None:
                self._append_log("Operacion cancelada.")
                return
            try:
                finished(result)
            except Exception as error:
                self._append_log("ERROR: " + str(error))
                QMessageBox.critical(self, "HidroCN", str(error))

        task = QgsTask.fromFunction(description, worker, on_finished=completed)
        self._current_task = task
        QgsApplication.taskManager().addTask(task)

    def _cancel_current_task(self):
        if self._current_task is not None:
            self._append_log("Cancelando operacion...")
            self._current_task.cancel()

    def _selected_project(self):
        project = self.project_edit.text().strip()
        if not project:
            QMessageBox.warning(self, "Google Earth Engine", "Ingrese el proyecto de Google Cloud.")
            return ""
        return project

    def _connect(self, force):
        project = self._selected_project()
        if not project:
            return
        self._save_settings()

        def done(result):
            suffix = "credenciales existentes" if result.get("reused") else "autorizacion nueva"
            self.connection_status.setText(f"Conectado a {project} ({suffix}).")
            self._append_log("Conexion correcta con " + project + ".")

        self._task(
            "Autenticando Earth Engine",
            lambda task: authenticate_ee_external(
                project, force, timeout_seconds=180, cancel_check=task.isCanceled
            ),
            done,
        )

    def _check_connection(self):
        project = self._selected_project()
        if not project:
            return
        self._save_settings()

        def done(result):
            self.connection_status.setText(
                f"Conexion verificada: {result['project']} | API {result.get('api_version') or 'disponible'}"
            )
            self._append_log("Earth Engine respondio correctamente.")

        self._task(
            "Comprobando conexion",
            lambda task: run_gee_external(
                "initialize",
                {"project_id": project},
                timeout_seconds=60,
                cancel_check=task.isCanceled,
            ),
            done,
        )

    def _source_changed(self):
        key = str(self.source_combo.currentData() or "")
        custom = key == "custom"
        self.custom_asset_edit.setEnabled(custom)
        self.custom_band_edit.setEnabled(custom)
        if key in SOURCE_CATALOG:
            definition = SOURCE_CATALOG[key]
            if definition.nominal_scale_m:
                self.scale_spin.setValue(definition.nominal_scale_m)
            self.source_note.setText(definition.notes)
        else:
            self.source_note.setText(
                "El asset personalizado se interpreta como CN-II. CN-I y CN-III seran derivados."
            )

    def _source_payload(self):
        return {
            "source_key": str(self.source_combo.currentData()),
            "custom_asset": self.custom_asset_edit.text().strip(),
            "custom_band": self.custom_band_edit.text().strip(),
        }

    def _inspect_source(self):
        project = self._selected_project()
        if not project:
            return
        payload = {"project_id": project, **self._source_payload()}

        def done(summary):
            lines = [summary["label"]]
            for condition, item in summary["assets"].items():
                lines.append(
                    f"CN-{condition}: {item['asset']} | bandas={', '.join(item['bands'])} | "
                    f"SRC={item['projection']} | escala={float(item['nominal_scale_m']):.2f} m"
                )
            if summary.get("notes"):
                lines.append(summary["notes"])
            self._append_log("\n".join(lines))

        self._task(
            "Inspeccionando fuente CN",
            lambda task: run_gee_external(
                "inspect", payload, timeout_seconds=120, cancel_check=task.isCanceled
            ),
            done,
        )

    def _use_active_layer(self):
        layer = self.iface.activeLayer() if self.iface else None
        if layer is None:
            QMessageBox.warning(self, "Cuenca", "No existe una capa activa.")
            return
        self.basin_combo.setLayer(layer)

    def _selected_features(self):
        layer = self.basin_combo.currentLayer()
        if layer is None:
            raise GeeError("Seleccione una capa poligonal de cuenca.")
        if not layer.crs().isValid():
            raise GeeError("La capa de cuenca no tiene un SRC valido.")
        if self.selected_only_check.isChecked():
            features = layer.selectedFeatures()
            if not features:
                raise GeeError(
                    "No hay poligonos seleccionados. Seleccione la cuenca en el mapa o desactive "
                    "'Procesar solo los elementos seleccionados'."
                )
        else:
            features = list(layer.getFeatures())
        if not features:
            raise GeeError("La capa o seleccion no contiene poligonos.")
        return layer, features

    def _selected_geometry(self):
        layer, features = self._selected_features()
        geometries = [
            feature.geometry()
            for feature in features
            if feature.hasGeometry() and not feature.geometry().isEmpty()
        ]
        if not geometries:
            raise GeeError("La seleccion no contiene geometrias poligonales validas.")
        geometry = QgsGeometry.unaryUnion(geometries)
        if geometry.isEmpty():
            raise GeeError("No fue posible unir la geometria de la cuenca.")
        repaired = False
        if not geometry.isGeosValid():
            geometry = geometry.makeValid()
            repaired = True
        if geometry.isEmpty():
            raise GeeError("La geometria siguio siendo invalida despues de repararla temporalmente.")
        return layer, geometry, len(geometries), repaired

    def _geometry_wgs84(self):
        layer, geometry, feature_count, repaired = self._selected_geometry()
        transform = QgsCoordinateTransform(
            layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance()
        )
        geometry = QgsGeometry(geometry)
        geometry.transform(transform)
        return json.loads(geometry.asJson(8)), geometry, feature_count, repaired

    def _validate_basin_clicked(self):
        try:
            _, geometry, feature_count, repaired = self._geometry_wgs84()
            area_km2 = geometry.area()  # Solo informativo en grados; GEE calcula el area real.
            centroid = geometry.centroid().asPoint()
            message = (
                f"Cuenca valida: {feature_count} geometria(s). Centroide WGS 84: "
                f"{centroid.x():.5f}, {centroid.y():.5f}."
            )
            if repaired:
                message += " Se uso una copia reparada temporalmente; la capa original no fue modificada."
            if area_km2 <= 0:
                message += " Revise la extension espacial antes de descargar."
            self._append_log(message)
            QMessageBox.information(self, "Cuenca", message)
        except Exception as error:
            QMessageBox.warning(self, "Cuenca", str(error))

    def _suggest_utm(self):
        try:
            _, geometry, _, _ = self._geometry_wgs84()
            centroid = geometry.centroid().asPoint()
            authid = suggested_utm_authid(centroid.x(), centroid.y())
            crs = QgsCoordinateReferenceSystem(authid)
            if not crs.isValid():
                raise GeeError(f"QGIS no pudo crear el SRC sugerido {authid}.")
            self.crs_widget.setCrs(crs)
            self._append_log(f"SRC sugerido desde el centroide: {authid} - {crs.description()}.")
        except Exception as error:
            QMessageBox.warning(self, "SRC", str(error))

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de salida", self.output_folder_edit.text().strip()
        )
        if folder:
            self.output_folder_edit.setText(folder)

    def _choose_lookup_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar tabla CN-II",
            self.local_lookup_edit.text().strip(),
            "Tabla CSV (*.csv);;Todos los archivos (*.*)",
        )
        if path:
            self.local_lookup_edit.setText(path)

    def _create_lookup_template(self):
        default_folder = self.output_folder_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar plantilla HEC-GeoHMS",
            str(Path(default_folder) / "tabla_CN_HEC_GeoHMS.csv"),
            "Tabla CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.local_lookup_edit.setText(write_lookup_template(path))
            self._append_log(
                "Plantilla creada. Complete una fila por codigo de uso del suelo con CN-II "
                "para los grupos A, B, C y D: " + path
            )
        except Exception as error:
            QMessageBox.warning(self, "Tabla CN", str(error))

    def _open_lookup_catalog(self):
        cursor_set = False
        try:
            lulc_path = self._local_raster_path(
                self.local_lulc_combo.currentLayer(), "uso del suelo"
            )
            QApplication.setOverrideCursor(Qt.WaitCursor)
            cursor_set = True
            try:
                codes = unique_integer_raster_values(lulc_path)
            finally:
                QApplication.restoreOverrideCursor()
                cursor_set = False
        except Exception as error:
            if cursor_set:
                QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Biblioteca CN-II", str(error))
            return
        default_folder = self.output_folder_edit.text().strip() or str(Path.home())
        dialog = CnTableBuilderDialog(codes, default_folder, self)
        if dialog.exec() == QDialog.Accepted and dialog.output_path:
            self.local_lookup_edit.setText(dialog.output_path)
            self._append_log(
                f"Tabla CN-II creada desde catalogo para {len(codes)} clases LULC: "
                + dialog.output_path
            )

    def _update_id_fields(self, *_args):
        previous = self.local_id_combo.currentText() if hasattr(self, "local_id_combo") else ""
        if not hasattr(self, "local_id_combo"):
            return
        self.local_id_combo.clear()
        self.local_id_combo.addItem("FID (identificador interno)", "")
        layer = self.basin_combo.currentLayer()
        if layer is not None:
            for field in layer.fields():
                self.local_id_combo.addItem(field.name(), field.name())
        index = self.local_id_combo.findText(previous)
        if index >= 0:
            self.local_id_combo.setCurrentIndex(index)

    @staticmethod
    def _local_raster_path(layer, label):
        if layer is None or not isinstance(layer, QgsRasterLayer) or not layer.isValid():
            raise LocalCnError(f"Seleccione un raster valido para {label}.")
        path = str(layer.source()).split("|", 1)[0]
        if not path or not Path(path).is_file():
            raise LocalCnError(
                f"{label} debe ser un raster local guardado en disco; no se admiten capas web o temporales."
            )
        return path

    def _local_conditions(self):
        conditions = []
        if self.local_dry_check.isChecked():
            conditions.append("I")
        if self.local_normal_check.isChecked():
            conditions.append("II")
        if self.local_wet_check.isChecked():
            conditions.append("III")
        if not conditions:
            raise LocalCnError("Seleccione al menos una condicion antecedente para el calculo local.")
        return conditions

    def _serialized_subbasins(self, output_crs):
        layer, features = self._selected_features()
        target = QgsCoordinateReferenceSystem(output_crs)
        transform = QgsCoordinateTransform(layer.crs(), target, QgsProject.instance())
        id_field = str(self.local_id_combo.currentData() or "")
        serialized = []
        seen = set()
        for feature in features:
            if not feature.hasGeometry() or feature.geometry().isEmpty():
                continue
            geometry = QgsGeometry(feature.geometry())
            if not geometry.isGeosValid():
                geometry = geometry.makeValid()
            if geometry.isEmpty():
                continue
            geometry.transform(transform)
            raw_identifier = feature[id_field] if id_field else feature.id()
            identifier = str(raw_identifier).strip()
            if not identifier or raw_identifier is None:
                raise LocalCnError(
                    f"El campo {id_field!r} contiene un identificador vacio. Complete sus valores o use FID."
                )
            if identifier in seen:
                raise LocalCnError(
                    f"El identificador de subcuenca no es unico: {identifier!r}. Seleccione otro campo."
                )
            seen.add(identifier)
            serialized.append({"id": identifier, "geometry": json.loads(geometry.asJson(8))})
        if not serialized:
            raise LocalCnError("No existen subcuencas validas para procesar.")
        return serialized, id_field

    def _calculate_local(self):
        try:
            lulc_path = self._local_raster_path(
                self.local_lulc_combo.currentLayer(), "uso del suelo"
            )
            hsg_path = self._local_raster_path(
                self.local_hsg_combo.currentLayer(), "grupo hidrologico HSG"
            )
            lookup_csv = self.local_lookup_edit.text().strip()
            if not lookup_csv or not Path(lookup_csv).is_file():
                raise LocalCnError("Seleccione una tabla CN-II CSV existente.")
            output_crs = self._output_crs()
            output_folder = self.output_folder_edit.text().strip()
            if not output_folder:
                raise LocalCnError("Seleccione una carpeta de salida.")
            features, id_field = self._serialized_subbasins(output_crs)
            conditions = self._local_conditions()
        except Exception as error:
            QMessageBox.warning(self, "HidroCN local", str(error))
            return

        self._save_settings()
        payload = {
            "lulc_path": lulc_path,
            "hsg_path": hsg_path,
            "lookup_csv": lookup_csv,
            "features": features,
            "id_field": id_field,
            "conditions": conditions,
            "output_crs": output_crs,
            "resolution_m": self.scale_spin.value(),
            "output_folder": output_folder,
            "prefix": self.prefix_edit.text().strip() or "hidrocn",
        }
        self._append_log(
            f"Calculo local: {len(features)} subcuenca(s); SRC {output_crs}; "
            f"malla de {self.scale_spin.value():.2f} m."
        )

        def done(result):
            lines = ["Construccion local completada."]
            for item in result.get("outputs", []):
                stats = item.get("statistics") or {}
                lines.append(
                    f"CN-{item['condition']}: {item['path']} | "
                    f"media={self._format_number(stats.get('mean'))}, "
                    f"rango={self._format_number(stats.get('minimum'))}-"
                    f"{self._format_number(stats.get('maximum'))}, "
                    f"cobertura={self._format_number(stats.get('coverage_pct'))}%"
                )
                if self.add_results_check.isChecked():
                    self._add_cn_raster(item["path"], item["condition"], stats)
            qc = result.get("quality_control") or {}
            lines.append(
                f"Control de calidad: {qc.get('matched_pixels', 0)} pixeles emparejados; "
                f"{qc.get('unmatched_pixels', 0)} sin correspondencia; "
                f"coincidencia={self._format_number(qc.get('match_pct'))}%."
            )
            if qc.get("unknown_lulc_values"):
                lines.append("Clases LULC ausentes en la tabla: " + str(qc["unknown_lulc_values"]))
            if qc.get("unexpected_hsg_values"):
                lines.append("Valores HSG fuera de 1-4: " + str(qc["unexpected_hsg_values"]))
            lines.append("Estadisticas por subcuenca: " + result["statistics_csv"])
            lines.append("Informe: " + result["report_path"])
            lines.append("Metadatos: " + result["metadata_path"])
            self._append_log("\n".join(lines))
            if self.add_results_check.isChecked():
                vector = QgsVectorLayer(result["subbasins_gpkg"], "Subcuencas CN", "ogr")
                if vector.isValid():
                    QgsProject.instance().addMapLayer(vector)
            message = f"Se generaron {len(result.get('outputs', []))} raster(s) y la tabla por subcuenca."
            if qc.get("unmatched_pixels"):
                message += " Revise el informe: existen combinaciones LULC-HSG sin correspondencia."
            QMessageBox.information(self, "HidroCN local", message)

        self._task(
            "Construyendo grid CN local",
            lambda task: None if task.isCanceled() else run_local_cn_workflow(payload),
            done,
        )

    def _conditions(self):
        conditions = []
        if self.dry_check.isChecked():
            conditions.append("I")
        if self.normal_check.isChecked():
            conditions.append("II")
        if self.wet_check.isChecked():
            conditions.append("III")
        if not conditions:
            raise GeeError("Seleccione al menos una condicion antecedente.")
        return conditions

    def _output_crs(self):
        crs = self.crs_widget.crs()
        if not crs.isValid():
            raise GeeError("Seleccione un SRC de salida valido.")
        if crs.isGeographic():
            raise GeeError(
                "El SRC de salida esta en coordenadas geograficas. Seleccione un SRC proyectado "
                "o use 'Sugerir UTM desde la cuenca'."
            )
        authid = crs.authid().upper()
        if not authid.startswith("EPSG:"):
            raise GeeError("Para esta version seleccione un SRC proyectado con codigo EPSG.")
        return authid

    def _download(self):
        project = self._selected_project()
        if not project:
            return
        try:
            geometry_geojson, geometry_wgs84, feature_count, repaired = self._geometry_wgs84()
            conditions = self._conditions()
            output_crs = self._output_crs()
            features, id_field = self._serialized_subbasins(output_crs)
            output_folder = self.output_folder_edit.text().strip()
            if not output_folder:
                raise GeeError("Seleccione una carpeta de salida.")
            prefix = self.prefix_edit.text().strip() or "hidrocn"
        except Exception as error:
            QMessageBox.warning(self, "HidroCN", str(error))
            return

        centroid = geometry_wgs84.centroid().asPoint()
        if str(self.source_combo.currentData()) == "cn_peru":
            if not (-82.5 <= centroid.x() <= -68.0 and -20.0 <= centroid.y() <= 1.5):
                answer = QMessageBox.question(
                    self,
                    "Cobertura CN Peru",
                    "El centroide parece estar fuera de Peru. ¿Desea intentar la descarga de todos modos?",
                )
                if answer != QMessageBox.Yes:
                    return

        self._save_settings()
        payload = {
            "project_id": project,
            **self._source_payload(),
            "geometry_geojson": geometry_geojson,
            "conditions": conditions,
            "output_crs": output_crs,
            "scale_m": self.scale_spin.value(),
            "output_folder": output_folder,
            "prefix": prefix,
            "features": features,
            "id_field": id_field,
        }
        self._append_log(
            f"Cuenca: {feature_count} geometria(s); SRC de salida: {output_crs}; "
            f"resolucion: {self.scale_spin.value():.2f} m."
        )
        if repaired:
            self._append_log("La geometria se reparo solo en memoria; la capa original no cambio.")

        def done(result):
            lines = ["Descarga completada."]
            for item in result.get("outputs", []):
                stats = item.get("statistics") or {}
                origin = "derivado" if item.get("derived") else "nativo/original"
                lines.append(
                    f"CN-{item['condition']} ({origin}): {item['path']} | "
                    f"media={self._format_number(stats.get('mean'))}, "
                    f"rango={self._format_number(stats.get('minimum'))}-"
                    f"{self._format_number(stats.get('maximum'))}, "
                    f"cobertura={self._format_number(stats.get('coverage_pct'))}%"
                )
                if self.add_results_check.isChecked():
                    self._add_cn_raster(item["path"], item["condition"], stats)
            if result.get("statistics_csv"):
                lines.append("Estadisticas por subunidad: " + result["statistics_csv"])
            if result.get("subbasins_gpkg"):
                lines.append("Subunidades con estadisticas: " + result["subbasins_gpkg"])
                if self.add_results_check.isChecked():
                    vector = QgsVectorLayer(
                        result["subbasins_gpkg"], "Subunidades CN GEE", "ogr"
                    )
                    if vector.isValid():
                        QgsProject.instance().addMapLayer(vector)
            lines.append("Metadatos: " + str(result.get("metadata_path", "")))
            self._append_log("\n".join(lines))
            QMessageBox.information(
                self,
                "HidroCN",
                f"Se generaron {len(result.get('outputs', []))} raster(s) CN y las "
                f"estadisticas de {len(result.get('subbasin_statistics', []))} subunidad(es).",
            )

        self._task(
            "Descargando mapas CN",
            lambda task: run_gee_external(
                "download", payload, timeout_seconds=900, cancel_check=task.isCanceled
            ),
            done,
        )

    @staticmethod
    def _format_number(value):
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "sin datos"

    def _add_cn_raster(self, path, condition, remote_stats=None):
        name = f"CN-{condition} {Path(path).stem}"
        layer = QgsRasterLayer(str(path), name)
        if not layer.isValid():
            self._append_log("No se pudo cargar automaticamente: " + str(path))
            return
        provider = layer.dataProvider()
        stats = provider.bandStatistics(
            1,
            QgsRasterBandStats.Min | QgsRasterBandStats.Max,
            layer.extent(),
            0,
        )
        minimum = stats.minimumValue
        maximum = stats.maximumValue
        try:
            minimum = float(minimum)
            maximum = float(maximum)
            if not (0 < minimum <= maximum <= 100):
                raise ValueError
        except (TypeError, ValueError):
            remote_stats = remote_stats or {}
            minimum = float(remote_stats.get("minimum"))
            maximum = float(remote_stats.get("maximum"))
        span = maximum - minimum
        if span <= 0:
            span = 1.0

        def ramp_value(fraction):
            return minimum + span * fraction

        ramp = QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList(
            [
                QgsColorRampShader.ColorRampItem(
                    ramp_value(0.00), QColor("#57cc0f"), f"{ramp_value(0.00):.2f}"
                ),
                QgsColorRampShader.ColorRampItem(
                    ramp_value(0.25), QColor("#abdda4"), f"{ramp_value(0.25):.2f}"
                ),
                QgsColorRampShader.ColorRampItem(
                    ramp_value(0.50), QColor("#ffffbf"), f"{ramp_value(0.50):.2f}"
                ),
                QgsColorRampShader.ColorRampItem(
                    ramp_value(0.75), QColor("#fdae61"), f"{ramp_value(0.75):.2f}"
                ),
                QgsColorRampShader.ColorRampItem(
                    maximum, QColor("#e1313d"), f"{maximum:.2f}"
                ),
            ]
        )
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(ramp)
        renderer = QgsSingleBandPseudoColorRenderer(provider, 1, shader)
        if hasattr(renderer, "setClassificationMin"):
            renderer.setClassificationMin(minimum)
        if hasattr(renderer, "setClassificationMax"):
            renderer.setClassificationMax(maximum)
        layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(layer)
        layer.triggerRepaint()
