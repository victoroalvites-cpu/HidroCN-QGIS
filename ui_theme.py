"""Paletas locales de HidroCN; no cambian el tema global de QGIS."""


def stylesheet(dark: bool) -> str:
    colors = (
        {
            "background": "#101d22", "surface": "#1b2b31", "surface_alt": "#23383e",
            "text": "#e9f3f1", "muted": "#b4c9c8", "border": "#415c61",
            "accent": "#59c3b3", "accent_hover": "#77d5c6", "button_text": "#102321",
            "selection": "#236b67", "disabled": "#34484d", "disabled_text": "#8da5a7",
            "log": "#14252a", "tab": "#1d3036",
        }
        if dark else
        {
            "background": "#edf4f1", "surface": "#ffffff", "surface_alt": "#e1eeea",
            "text": "#203b3b", "muted": "#526d6c", "border": "#c5d9d4",
            "accent": "#147e73", "accent_hover": "#0f6b62", "button_text": "#ffffff",
            "selection": "#cae9e2", "disabled": "#d4e0dc", "disabled_text": "#6b8381",
            "log": "#f8fbfa", "tab": "#e5f0ec",
        }
    )
    return """
QDialog {{ background: {background}; color: {text}; }}
QWidget#HidroCNHeader, QWidget#HidroCNContent {{ background: {background}; }}
QLabel {{ color: {text}; }}
QLabel#HidroCNTitle {{ color: {accent}; font-size: 25px; font-weight: 800; }}
QLabel#HidroCNSubtitle, QLabel#HidroCNHint {{ color: {muted}; }}
QLabel#HidroCNProgressLabel {{ color: {accent}; font-weight: 600; }}
QGroupBox {{ background: {surface}; border: 1px solid {border}; border-radius: 10px;
             margin-top: 18px; padding: 16px 12px 12px; color: {accent}; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 13px; padding: 0 6px; }}
QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit, QTableWidget {{
    background: {surface}; color: {text}; border: 1px solid {border};
    border-radius: 6px; padding: 5px; min-height: 20px;
}}
QComboBox QAbstractItemView {{ background: {surface}; color: {text};
    selection-background-color: {selection}; selection-color: {text}; }}
QPushButton {{ background: {surface_alt}; color: {text}; border: 1px solid {border};
    border-radius: 7px; padding: 7px 11px; min-height: 22px; font-weight: 600; }}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton[role="primary"] {{ background: {accent}; color: {button_text}; border-color: {accent}; }}
QPushButton[role="primary"]:hover {{ background: {accent_hover}; }}
QPushButton[role="danger"] {{ color: {accent}; }}
QPushButton:disabled {{ background: {disabled}; color: {disabled_text}; border-color: {disabled}; }}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px;
    background: {surface}; top: -1px; }}
QTabWidget::tab-bar {{ left: 8px; }}
QTabBar::tab {{ background: {tab}; color: {muted}; border: 1px solid {border};
    padding: 9px 16px; min-width: 150px;
    border-top-left-radius: 7px; border-top-right-radius: 7px; }}
QTabBar::tab:selected {{ background: {surface}; color: {accent}; font-weight: 700; }}
QTabBar::tab:hover {{ color: {accent}; }}
QProgressBar {{ background: {surface_alt}; color: {text}; border: 1px solid {border};
    border-radius: 6px; text-align: center; min-height: 14px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 5px; }}
QPlainTextEdit {{ background: {log}; font-family: Consolas, monospace; }}
QCheckBox {{ spacing: 6px; color: {text}; }}
QScrollArea {{ border: none; background: {background}; }}
QTableWidget {{ alternate-background-color: {surface_alt}; }}
""".format(**colors)
