"""Styles et couleurs communs de l'application."""

APP_QSS = """
QMainWindow, QWidget { background: #10151f; color: #e8ecf3; font-size: 14px; }
QLabel#title { font-size: 26px; font-weight: 700; color: #f5a623; }
QLabel#subtitle { color: #8b95a7; font-size: 15px; }
QLabel#hud_value { font-size: 34px; font-weight: 700; color: #ffffff; }
QLabel#hud_unit { font-size: 13px; color: #8b95a7; }
QLabel#big_value { font-size: 52px; font-weight: 800; color: #f5a623; }
QPushButton {
    background: #1d2637; color: #e8ecf3; border: 1px solid #2c3a52;
    border-radius: 8px; padding: 10px 20px; font-size: 14px;
}
QPushButton:hover { background: #27354d; }
QPushButton#primary { background: #f5a623; color: #10151f; font-weight: 700; border: none; }
QPushButton#primary:hover { background: #ffb733; }
QPushButton#danger { background: #97333f; color: #ffffff; border: none; }
QPushButton#danger:hover { background: #b13c4a; }
QListWidget, QTableWidget {
    background: #151c2a; border: 1px solid #2c3a52; border-radius: 8px;
}
QListWidget::item { padding: 12px; }
QListWidget::item:selected { background: #27354d; color: #ffffff; }
QHeaderView::section {
    background: #1d2637; color: #8b95a7; border: none; padding: 8px;
}
QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #151c2a; border: 1px solid #2c3a52; border-radius: 6px;
    padding: 6px 10px; color: #e8ecf3;
}
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: #151c2a; color: #8b95a7; padding: 10px 24px;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}
QTabBar::tab:selected { background: #27354d; color: #ffffff; }
QProgressBar {
    background: #151c2a; border: 1px solid #2c3a52; border-radius: 6px;
    text-align: center; color: #e8ecf3;
}
QProgressBar::chunk { background: #f5a623; border-radius: 5px; }
QDialog { background: #10151f; }
QGroupBox { border: 1px solid #2c3a52; border-radius: 8px; margin-top: 12px; }
QGroupBox::title { color: #8b95a7; }
QLabel#status_ok { color: #4cc38a; }
QLabel#status_err { color: #ef6476; }
"""


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_distance(meters: float) -> str:
    return f"{meters / 1000.0:.2f} km"


def format_speed(speed_kmh: float) -> str:
    return f"{speed_kmh:.1f}"


def format_power(watts: float) -> str:
    return f"{int(watts)}"
