"""Genera el manual tecnico y de usuario de HidroCN 0.5.0."""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Manual_Tecnico_y_de_Usuario_HidroCN_QGIS_v0.5.0.docx"
ICON = ROOT / "icon.png"

BLUE = "155B7A"
GREEN = "4D8F3A"
LIGHT_BLUE = "EAF4F8"
LIGHT_GREEN = "EDF5E9"
GRAY = "555555"
WHITE = "FFFFFF"


def shade(cell, color):
    tc_pr = cell._tc.get_or_add_tcPr()
    fill = tc_pr.find(qn("w:shd"))
    if fill is None:
        fill = OxmlElement("w:shd")
        tc_pr.append(fill)
    fill.set(qn("w:fill"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_cell_text(cell, text, bold=False, color=None, size=8.5):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(doc, headers, rows, widths=None, font_size=8.3):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for index, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[index], header, True, WHITE, font_size)
        shade(table.rows[0].cells[index], BLUE)
        if widths:
            table.rows[0].cells[index].width = Cm(widths[index])
    set_repeat_table_header(table.rows[0])
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            set_cell_text(cells[index], value, False, None, font_size)
            if widths:
                cells[index].width = Cm(widths[index])
            if row_index % 2:
                shade(cells[index], "F4F7F8")
    return table


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    relationship_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), BLUE)
    props.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Página ")
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = "PAGE"
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, end])


def set_picture_alt_text(inline_shape, title, description):
    drawing = inline_shape._inline
    doc_pr = drawing.docPr
    doc_pr.set("title", title)
    doc_pr.set("descr", description)


def add_heading(doc, text, level=1):
    heading = doc.add_heading(text, level=level)
    heading.paragraph_format.keep_with_next = True
    return heading


def add_body(doc, text, bold_lead=None):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.05
    if bold_lead and text.startswith(bold_lead):
        paragraph.add_run(bold_lead).bold = True
        paragraph.add_run(text[len(bold_lead):])
    else:
        paragraph.add_run(text)
    return paragraph


def add_bullets(doc, items):
    for item in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(item)


def add_steps(doc, items):
    for number, item in enumerate(items, 1):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.7)
        paragraph.paragraph_format.first_line_indent = Cm(-0.7)
        paragraph.paragraph_format.space_after = Pt(3)
        lead = paragraph.add_run(f"{number}.  ")
        lead.bold = True
        paragraph.add_run(item)


def add_note(doc, title, text, color=LIGHT_BLUE):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    shade(cell, color)
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(title + ": ")
    run.bold = True
    paragraph.add_run(text)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def new_page(doc, title, subtitle=None):
    doc.add_page_break()
    add_heading(doc, title, 1)
    if subtitle:
        paragraph = doc.add_paragraph(subtitle)
        paragraph.style = doc.styles["Subtitle"]
    return doc


def configure_document(doc):
    section = doc.sections[0]
    section.top_margin = Cm(1.65)
    section.bottom_margin = Cm(1.55)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    section.header_distance = Cm(0.65)
    section.footer_distance = Cm(0.65)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9.2)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.05
    for style_name, size, color in (
        ("Title", 26, BLUE),
        ("Subtitle", 12, GRAY),
        ("Heading 1", 17, BLUE),
        ("Heading 2", 12, GREEN),
        ("Heading 3", 10, BLUE),
    ):
        style = styles[style_name]
        style.font.name = "Aptos Display" if "Heading" in style_name or style_name == "Title" else "Aptos"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = style_name != "Subtitle"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), style.font.name)
    for list_style in ("List Bullet", "List Number"):
        styles[list_style].font.name = "Aptos"
        styles[list_style].font.size = Pt(9)

    doc.core_properties.title = "Manual técnico y de usuario HidroCN QGIS 0.5.0"
    doc.core_properties.subject = "Instalación, entradas, operación, resultados y control de calidad de HidroCN"
    doc.core_properties.author = "Victor Olivos"
    doc.core_properties.keywords = "QGIS, HidroCN, SCS-CN, HEC-GeoHMS, Google Earth Engine"
    doc.core_properties.comments = "Documento público de la versión estable 0.5.0"

    settings = doc.settings.element
    theme_font_lang = settings.find(qn("w:themeFontLang"))
    if theme_font_lang is None:
        theme_font_lang = OxmlElement("w:themeFontLang")
        settings.append(theme_font_lang)
    theme_font_lang.set(qn("w:val"), "es-PE")

    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = "HidroCN 0.5.0  |  Manual técnico y de usuario"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.runs[0].font.size = Pt(8)
    paragraph.runs[0].font.color.rgb = RGBColor.from_string(GRAY)
    add_page_number(section.footer.paragraphs[0])


def build():
    doc = Document()
    configure_document(doc)

    # 1. Portada
    doc.add_paragraph().paragraph_format.space_after = Pt(22)
    picture = doc.add_picture(str(ICON), width=Inches(1.45))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_picture_alt_text(
        picture,
        "Icono de HidroCN",
        "Icono del complemento HidroCN con una cuenca, drenaje y las letras CN.",
    )
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("HidroCN – Curva Número")
    subtitle = doc.add_paragraph(style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Manual técnico y de usuario")
    version = doc.add_paragraph()
    version.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = version.add_run("Versión pública estable 0.5.0")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor.from_string(GREEN)
    doc.add_paragraph().paragraph_format.space_after = Pt(34)
    add_table(
        doc,
        ["Dato", "Valor"],
        [
            ("Autor", "Victor Olivos"),
            ("Compatibilidad", "QGIS 3.28–3.99"),
            ("Licencia", "GNU GPL v3 o posterior"),
            ("Fecha", "14 de septiembre de 2026"),
            ("Repositorio", "github.com/victoroalvites-cpu/HidroCN-QGIS"),
        ],
        [4.2, 11.5],
        9,
    )
    add_note(
        doc,
        "Propósito",
        "Obtener mapas SCS-CN reproducibles mediante descarga desde Google Earth Engine o cálculo local tipo HEC-GeoHMS, y resumirlos por cuenca o subcuenca.",
        LIGHT_GREEN,
    )

    # 2. Control y contenido
    new_page(doc, "Control del documento")
    add_table(
        doc,
        ["Versión", "Estado", "Descripción"],
        [
            ("0.5.0", "Pública estable", "Manual consolidado para la primera publicación pública."),
            ("0.4.1", "Previa", "Fórmulas ANA de conversión de condiciones antecedentes."),
            ("0.4.0", "Previa", "Icono propio y estadísticas por subunidad para GEE."),
        ],
        [2.2, 3.1, 10.4],
    )
    add_heading(doc, "Contenido", 2)
    add_table(
        doc,
        ["Sección", "Página"],
        [
            ("1. Alcance y conceptos", "3"),
            ("2. Instalación", "4"),
            ("3. Cuenca, subcuencas y SRC", "5"),
            ("4. Entradas del cálculo local", "6"),
            ("5. Biblioteca ANA / NumCurv", "7"),
            ("6. Flujo local HEC-GeoHMS", "8"),
            ("7. Descarga desde Google Earth Engine", "9"),
            ("8. Condiciones CN y fórmulas", "10"),
            ("9. Salidas y estadísticas areales", "11"),
            ("10. Control de calidad", "12"),
            ("11. Solución de problemas", "13"),
            ("12. Notas técnicas y seguridad", "14"),
            ("13. Referencias y soporte", "15"),
        ],
        [13.4, 2.1],
    )

    # 3. Alcance
    new_page(doc, "1. Alcance y conceptos")
    add_body(doc, "HidroCN ofrece dos rutas independientes para producir mapas de número de curva SCS. Ambas parten de una capa poligonal y generan GeoTIFF en un SRC proyectado elegido por el usuario.")
    add_table(
        doc,
        ["Ruta", "Entradas principales", "Uso recomendado"],
        [
            ("Desde GEE", "Cuenca, proyecto Google Cloud, fuente CN y resolución", "Obtener rápidamente CN Perú, GCN250 o un asset propio."),
            ("Local HEC-GeoHMS", "Cuenca, LULC, HSG y tabla CN A–D", "Controlar la correspondencia de coberturas y construir el grid local."),
        ],
        [3.2, 6.2, 6.1],
    )
    add_heading(doc, "Conceptos esenciales", 2)
    add_bullets(
        doc,
        [
            "CN-II representa la condición antecedente normal o promedio y es la base del cálculo local.",
            "CN-I y CN-III representan condiciones seca y húmeda; pueden ser productos nativos de GCN250 o derivados de CN-II, según la fuente.",
            "LULC es el raster de uso o cobertura del suelo. Sus códigos dependen del producto y no tienen una equivalencia universal.",
            "HSG es el grupo hidrológico del suelo, codificado en HidroCN como 1=A, 2=B, 3=C y 4=D.",
            "La estadística areal es la media de celdas válidas asignadas a cada subunidad, no el promedio de los mínimos y máximos.",
        ],
    )
    add_note(doc, "Decisión", "Use GEE cuando necesite un producto CN ya elaborado. Use el cálculo local cuando deba justificar la relación entre cobertura, suelo y CN.")

    # 4. Instalación
    new_page(doc, "2. Instalación")
    add_heading(doc, "Desde el repositorio oficial de complementos", 2)
    add_steps(
        doc,
        [
            "Abra Complementos > Administrar e instalar complementos en QGIS.",
            "Busque HidroCN - Curva Numero.",
            "Pulse Instalar complemento y cierre el administrador.",
            "Abra HidroCN desde la barra de herramientas o el menú Complementos > HidroCN.",
        ],
    )
    add_heading(doc, "Instalación manual desde ZIP", 2)
    add_steps(doc, ["Descargue el archivo HidroCN_QGIS_v0.5.0.zip.", "En el administrador, elija Instalar desde ZIP.", "Seleccione el archivo, confirme la advertencia si procede y active HidroCN."])
    add_heading(doc, "Dependencia opcional para Google Earth Engine", 2)
    add_body(doc, "El cálculo local funciona con NumPy y GDAL/OGR incluidos en QGIS. Solo la ruta GEE requiere earthengine-api en el Python de QGIS.")
    add_table(
        doc,
        ["Entorno", "Comando orientativo"],
        [("PowerShell", '& "RUTA\\A\\QGIS\\apps\\Python312\\python.exe" -m pip install --user "earthengine-api>=1.5,<2"')],
        [3.2, 12.3],
        8,
    )
    add_note(doc, "Importante", "En PowerShell, el operador & debe ir antes de una ruta ejecutable entre comillas. Use el botón Cómo instalar la API para copiar el comando adaptado a su QGIS y reinicie QGIS después.")

    # 5. Cuenca y CRS
    new_page(doc, "3. Cuenca, subcuencas y SRC")
    add_heading(doc, "Capa poligonal", 2)
    add_bullets(doc, ["Debe contener geometrías poligonales válidas.", "Puede representar una cuenca única o varias subcuencas.", "Active Procesar solo los elementos seleccionados para limitar el análisis.", "Elija un identificador único y no vacío para conservar la trazabilidad de cada subunidad."])
    add_heading(doc, "Sistema de referencia", 2)
    add_body(doc, "La capa de entrada puede estar en coordenadas geográficas o proyectadas. HidroCN transforma temporalmente la geometría a WGS 84 para enviarla a GEE y guarda los resultados en el SRC proyectado seleccionado.")
    add_table(
        doc,
        ["Elemento", "SRC utilizado"],
        [
            ("Geometría enviada a GEE", "WGS 84 (EPSG:4326), de forma temporal; no se crea un asset de la cuenca."),
            ("GeoTIFF de salida", "SRC proyectado seleccionado en HidroCN, por ejemplo WGS 84 / UTM 18S."),
            ("Cálculo local", "Malla común en el SRC proyectado y resolución elegidos."),
        ],
        [4.2, 11.3],
    )
    add_note(doc, "UTM", "Use Sugerir UTM desde la cuenca y compruebe que el huso sea apropiado si la cuenca cruza un límite de zona.")

    # 6. Inputs local
    new_page(doc, "4. Entradas del cálculo local")
    add_table(
        doc,
        ["Entrada", "Requisito", "Control previo"],
        [
            ("LULC", "Raster con códigos enteros de cobertura", "Verificar leyenda, fecha y fuente."),
            ("HSG", "Raster con valores 1=A, 2=B, 3=C, 4=D", "Reclasificar otros códigos; resolver grupos dobles."),
            ("Tabla CN", "CSV con LUValue, Description, A, B, C, D", "Cada código LULC utilizado debe tener una fila válida."),
            ("Subcuencas", "Polígonos con identificador único", "Reparar geometrías y evitar solapes."),
        ],
        [3.2, 6.3, 6.0],
    )
    add_heading(doc, "Resolución y alineación", 2)
    add_body(doc, "LULC y HSG no necesitan tener inicialmente el mismo tamaño de píxel que un DEM. HidroCN los reproyecta, recorta y alinea a una malla común definida por el SRC, la extensión ajustada de la cuenca y la resolución de salida.")
    add_bullets(doc, ["Se usa vecino más cercano para preservar códigos categóricos.", "Elegir una resolución menor que la fuente no crea detalle nuevo.", "La resolución debe ser coherente con la fuente más gruesa y el objetivo del estudio.", "Las celdas sin combinación definida quedan como NoData (-9999), no reciben un CN inventado."])
    add_note(doc, "DEM", "HidroCN 0.5.0 no necesita un DEM para construir el grid CN. El DEM pertenece a otros pasos de modelación, como delimitación o pendientes.")

    # 7. Catálogos
    new_page(doc, "5. Biblioteca ANA / NumCurv")
    add_body(doc, "La biblioteca ayuda a construir la tabla CN requerida por el cálculo local. Detecta los códigos enteros presentes en LULC y permite asignar una categoría documentada a cada código.")
    add_table(
        doc,
        ["Catálogo visible", "Contenido", "Criterio de uso"],
        [
            ("ANA 2015 - Tabla 4 del modelo", "13 coberturas y valores A–D transcritos del documento ANA0004219.", "Adecuar cada clase LULC a la cobertura ANA más defendible."),
            ("NUMCURV - Tabla general", "Coberturas, tratamiento y condición hidrológica de la tabla general.", "Usar cuando la descripción y manejo coincidan con el estudio."),
            ("NUMCURV - Tabla de zonas áridas", "Clases de vegetación y condición para ambientes áridos.", "Usar con justificación en zonas áridas o semiáridas."),
        ],
        [5.1, 5.8, 4.6],
    )
    add_heading(doc, "Ejemplo: ESA WorldCover", 2)
    add_body(doc, "Los códigos ESA (10 árboles, 20 matorral, 30 pastizal, 40 cultivos, 50 urbano, 60 suelo desnudo, 70 nieve/hielo, 80 agua y 90 humedal) describen coberturas, pero no fijan por sí mismos el tratamiento ni la condición hidrológica. En la cuenca Lurín debe revisarse cada equivalencia según campo, escala y propósito.")
    add_note(doc, "Regla", "Cambiar de MINAM a ESA WorldCover u otro producto cambia los códigos y puede cambiar las equivalencias. La tabla CN debe revisarse; no basta con reutilizarla por posición de fila.")

    # 8. Local workflow
    new_page(doc, "6. Flujo local HEC-GeoHMS")
    add_steps(
        doc,
        [
            "Seleccione la capa de cuenca o subcuencas y, si corresponde, los elementos seleccionados.",
            "Abra la pestaña Cálculo local HEC-GeoHMS.",
            "Seleccione LULC, HSG y el campo identificador de subunidad.",
            "Seleccione una tabla CSV, cree una plantilla o abra Biblioteca ANA / NumCurv.",
            "Asigne todos los códigos LULC utilizados y revise los valores A–D.",
            "Marque CN-I, CN-II y/o CN-III.",
            "Defina SRC proyectado, resolución, carpeta y prefijo de salida.",
            "Pulse Construir CN local y revise el registro, el informe HTML y el control de calidad.",
        ],
    )
    add_heading(doc, "Regla de cruce", 2)
    add_body(doc, "Para cada celda válida, HidroCN lee el código LULC, obtiene la fila correspondiente de la tabla y elige la columna A, B, C o D según el valor HSG. El resultado base es CN-II.")
    add_table(
        doc,
        ["LULC", "HSG", "Fila/columna", "Resultado"],
        [("40 (cultivo)", "2 (B)", "LUValue=40, columna B", "CN-II asignado por la tabla"), ("Código sin fila", "Cualquiera", "Sin correspondencia", "NoData y advertencia"), ("Código válido", "5", "HSG fuera de 1–4", "NoData y advertencia")],
        [2.6, 2.3, 5.2, 5.4],
    )

    # 9. GEE
    new_page(doc, "7. Descarga desde Google Earth Engine")
    add_steps(
        doc,
        [
            "Seleccione la capa poligonal y el identificador de subunidad.",
            "Ingrese un proyecto Google Cloud habilitado para Earth Engine.",
            "Pulse Conectar / autorizar y complete personalmente el acceso en el navegador.",
            "Seleccione CN Perú, GCN250 o un asset personalizado y, si aplica, la banda.",
            "Marque las condiciones, el SRC proyectado, la resolución, carpeta y prefijo.",
            "Pulse Descargar CN y espere la confirmación de rasters, metadatos y estadísticas.",
        ],
    )
    add_table(
        doc,
        ["Fuente", "Condiciones", "Escala nominal", "Alcance"],
        [
            ("CN Perú", "CN-II nativo; CN-I y CN-III derivados", "90 m", "Perú; asset projects/ee-mportuguezm/assets/CN_Peru"),
            ("GCN250", "Dry, Average y Wet nativos", "250 m", "Cobertura propia del producto GCN250"),
            ("Asset personalizado", "Primera banda o banda indicada como CN-II", "Definida por el usuario", "Depende del asset y sus permisos"),
        ],
        [3.1, 4.4, 3.0, 5.0],
    )
    add_note(doc, "Autorización", "HidroCN no solicita, lee ni almacena contraseñas. La sesión de Earth Engine depende del usuario y de los permisos de su proyecto/asset.")

    # 10. Fórmulas
    new_page(doc, "8. Condiciones CN y fórmulas")
    add_body(doc, "Cuando la fuente ofrece solo CN-II, HidroCN estima las otras condiciones celda por celda con las relaciones publicadas por ANA (2015):")
    equations = doc.add_table(rows=2, cols=1)
    equations.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_cell_text(equations.cell(0, 0), "CN(I) = 4,2 × CN(II) / [10 − 0,058 × CN(II)]", True, BLUE, 13)
    set_cell_text(equations.cell(1, 0), "CN(III) = 23 × CN(II) / [10 + 0,13 × CN(II)]", True, GREEN, 13)
    shade(equations.cell(0, 0), LIGHT_BLUE)
    shade(equations.cell(1, 0), LIGHT_GREEN)
    doc.add_paragraph()
    add_body(doc, "Los valores se mantienen en el intervalo físico (0, 100]. Los metadatos distinguen productos nativos/originales de productos derivados.")
    add_heading(doc, "Retención potencial", 2)
    add_body(doc, "Si se necesita la retención potencial máxima en sistema internacional, puede calcularse como S = (25400 − 254 × CN) / CN, equivalente a S = 25400/CN − 254, con S en milímetros.")
    add_table(
        doc,
        ["Fuente", "CN-I", "CN-II", "CN-III"],
        [("CN Perú", "Derivado", "Nativo", "Derivado"), ("GCN250", "Nativo Dry", "Nativo Average", "Nativo Wet"), ("Asset personalizado", "Derivado", "Nativo declarado", "Derivado")],
        [4.0, 3.8, 3.8, 3.8],
    )
    add_note(doc, "No confundir", "La fórmula de S no convierte condiciones antecedentes; transforma un CN concreto en retención potencial.")

    # 11. Outputs
    new_page(doc, "9. Salidas y estadísticas areales")
    add_table(
        doc,
        ["Producto", "Formato", "Contenido"],
        [
            ("CN-I / CN-II / CN-III", "GeoTIFF", "Raster proyectado, recortado y con NoData -9999 fuera de la cuenca."),
            ("Estadísticas", "CSV", "Una fila por subunidad y campos de media, mínimo, máximo, cobertura y píxeles."),
            ("Subunidades CN", "GeoPackage", "Geometría original con campos estadísticos de cada condición."),
            ("Metadatos", "JSON", "Fuente, escala, SRC, condición, derivación y rutas de salida."),
            ("Informe local", "HTML", "Entradas, calidad del cruce y advertencias del cálculo local."),
        ],
        [4.1, 2.7, 8.7],
    )
    add_heading(doc, "Cómo se calcula la media areal", 2)
    add_body(doc, "Para cada polígono se promedian los valores de las celdas válidas cuyo centro cae en la subunidad. Como la malla está en un SRC proyectado y todas las celdas tienen igual área, la media de píxeles equivale a una media ponderada por área:")
    add_body(doc, "CN_areal = Σ(CNᵢ × Aᵢ) / ΣAᵢ. En una malla regular, Aᵢ es constante y se simplifica a ΣCNᵢ / n.")
    add_note(doc, "Diferencias con Propiedades del raster", "La media global de QGIS puede incluir todas las celdas válidas de la extensión del archivo y mostrar VALID_PERCENT respecto al rectángulo. HidroCN calcula por cada polígono y su campo COV expresa cobertura válida dentro de esa subunidad.")

    # 12. QA
    new_page(doc, "10. Control de calidad")
    add_heading(doc, "Antes de ejecutar", 2)
    add_bullets(doc, ["Geometrías válidas, identificadores únicos y sin solapes.", "SRC proyectado apropiado y resolución coherente con las fuentes.", "LULC categórico con códigos enteros; HSG limitado a 1–4.", "Tabla con una sola fila por LUValue y valores CN en (0, 100].", "Permisos de Earth Engine verificados si se usa GEE."])
    add_heading(doc, "Después de ejecutar", 2)
    add_bullets(doc, ["Confirmar que el raster termina exactamente en la cuenca y que el exterior es transparente/NoData.", "Revisar rango, media y cobertura por subunidad; investigar coberturas bajas.", "Comparar visualmente zonas urbanas, agua, nieve, bosque y cultivos con la cobertura de entrada.", "Abrir el JSON y el informe HTML para conservar la trazabilidad.", "No interpretar la paleta 0–100 como rango estadístico: la simbología debe usar el mínimo y máximo válidos."])
    add_table(
        doc,
        ["Indicador", "Interpretación"],
        [("COV cercano a 100 %", "La mayor parte de la subunidad tiene valores CN válidos."), ("COV bajo", "Hay NoData, combinaciones LULC-HSG no definidas o falta de cobertura de la fuente."), ("-inf en valores únicos", "Indica un NoData/valor no finito mal interpretado; HidroCN normaliza a -9999."), ("Mínimo y máximo iguales", "La subunidad contiene una sola clase CN o muy pocos píxeles válidos.")],
        [4.3, 11.2],
    )

    # 13. Troubleshooting
    new_page(doc, "11. Solución de problemas")
    add_table(
        doc,
        ["Síntoma", "Causa probable", "Acción"],
        [
            ("Token -m inesperado en PowerShell", "Falta el operador & antes del ejecutable entre comillas.", "Use & \"ruta\\python.exe\" -m pip ..."),
            ("earthengine-api no disponible", "Paquete no instalado en el Python que usa QGIS.", "Use Cómo instalar la API y reinicie QGIS."),
            ("Acceso denegado al asset", "Proyecto, cuenta o asset sin permisos.", "Cambie autorización o solicite acceso al propietario."),
            ("CN-I/III cubren la extensión", "NoData no normalizado en una salida previa.", "Regenerar con 0.5.0 y verificar -9999 fuera de la cuenca."),
            ("Clases LULC ausentes", "La tabla no contiene todos los códigos del raster.", "Complete la biblioteca/CSV; no suprima la advertencia."),
            ("Media distinta de Propiedades", "Estadística global frente a estadística por polígono.", "Use el CSV/GeoPackage de HidroCN para CN areal."),
            ("Descarga demasiado grande", "Límite de descarga directa de GEE.", "Aumente resolución o divida el área de forma controlada."),
        ],
        [4.2, 5.5, 5.8],
        7.7,
    )
    add_note(doc, "Reporte", "Al abrir una incidencia, adjunte versión de QGIS, sistema operativo, fuente, SRC, resolución, registro completo y un caso mínimo que pueda compartirse legalmente.")

    # 14. Technical/security
    new_page(doc, "12. Notas técnicas y seguridad")
    add_heading(doc, "Implementación", 2)
    add_bullets(doc, ["Reproyección y alineación categórica mediante GDAL/OGR y vecino más cercano.", "Cálculo matricial con NumPy; NoData estándar -9999 en salidas raster.", "Descarga GEE mediante earthengine-api y URL temporal; la cuenca no se registra como asset.", "Estadísticas zonales generadas de forma homogénea para el flujo local y el flujo GEE.", "Metadatos públicos de versión, fuente, condición y método de derivación."])
    add_heading(doc, "Privacidad y credenciales", 2)
    add_body(doc, "HidroCN no incluye claves, tokens ni contraseñas. La autorización se realiza en el navegador del usuario. Los identificadores de proyecto y asset pueden aparecer en los metadatos para reproducibilidad; el acceso real sigue controlado por Google Earth Engine.")
    add_heading(doc, "Limitaciones de 0.5.0", 2)
    add_bullets(doc, ["Las entradas LULC y HSG locales deben ser rasters guardados en disco.", "El origen de la malla se ajusta a la extensión/resolución; no se hereda de un DEM de referencia.", "En subcuencas solapadas prevalece la última geometría rasterizada.", "La descarga GEE es directa y no implementa mosaico automático por teselas.", "No exporta HEC-DSS ni sustituye la revisión hidrológica de equivalencias LULC."])

    # 15. References/support
    new_page(doc, "13. Referencias y soporte")
    add_heading(doc, "Referencias metodológicas", 2)
    references = [
        ("ANA (2015). Generación del mapa temático de Curva Número (CN), tabla 4 y relaciones de condiciones antecedentes.", "Repositorio institucional de la ANA", "https://repositorio.ana.gob.pe/"),
        ("USDA NRCS. National Engineering Handbook, Part 630, Chapter 9: Hydrologic Soil-Cover Complexes.", "Capítulo 9 del manual NRCS", "https://directives.nrcs.usda.gov/sites/default/files2/1712930607/7306.pdf"),
        ("HEC-GeoHMS User's Manual 10.1 y documentación HEC-HMS sobre Curve Number Grid.", "Documentación oficial HEC-HMS", "https://www.hec.usace.army.mil/confluence/hmsdocs/"),
        ("GCN250: Global Curve Number dataset, assets de Dry, Average y Wet.", "Ficha comunitaria de GCN250", "https://gee-community-catalog.org/projects/gcn250/"),
        ("SCS-CN Builder, referencia funcional GPL-3.0-or-later.", "Repositorio de SCS-CN Builder", "https://github.com/nikolavdjokic995-ctrl/SCS-CN-Builder"),
    ]
    for label, link_text, url in references:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.add_run(label + " ")
        add_hyperlink(paragraph, link_text, url)
    add_heading(doc, "Proyecto y soporte", 2)
    for label, link_text, url in (
        ("Código fuente", "Repositorio público de HidroCN", "https://github.com/victoroalvites-cpu/HidroCN-QGIS"),
        ("Reporte de incidencias", "Registro de incidencias de HidroCN", "https://github.com/victoroalvites-cpu/HidroCN-QGIS/issues"),
        ("Portal de complementos QGIS", "Portal oficial de complementos QGIS", "https://plugins.qgis.org/"),
    ):
        paragraph = doc.add_paragraph()
        paragraph.add_run(label + ": ").bold = True
        add_hyperlink(paragraph, link_text, url)
    add_note(doc, "Licencia", "HidroCN se distribuye bajo GNU GPL v3 o posterior. Las fuentes de datos externas mantienen sus propias condiciones de uso y atribución.", LIGHT_GREEN)
    add_heading(doc, "Lista final", 2)
    add_bullets(doc, ["Datos y equivalencias documentados.", "Rango y cobertura revisados.", "JSON, CSV/GeoPackage e informe conservados con el proyecto.", "Versión de HidroCN y QGIS registrada para reproducibilidad."])

    # Mark every first table row so assistive technologies can orient users,
    # including single-cell callouts and formula panels.
    for table in doc.tables:
        set_repeat_table_header(table.rows[0])

    # Apply common language to all runs.
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            r_pr = run._r.get_or_add_rPr()
            lang = r_pr.find(qn("w:lang"))
            if lang is None:
                lang = OxmlElement("w:lang")
                r_pr.append(lang)
            lang.set(qn("w:val"), "es-PE")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
