"""Dark theme for the simulator (matches the dark pyqtgraph plots)."""
import pyqtgraph as pg
from PySide6.QtGui import QColor, QPalette


def apply_dark_theme(app):
    pg.setConfigOptions(background="#1b1b1b", foreground="#d0d0d0", antialias=True)
    app.setStyle("Fusion")
    text = QColor("#e0e0e0")
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#232323"))
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, QColor("#2b2b2b"))
    p.setColor(QPalette.AlternateBase, QColor("#232323"))
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor("#333333"))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.Highlight, QColor("#2a7fb8"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor("#2b2b2b"))
    p.setColor(QPalette.ToolTipText, text)
    app.setPalette(p)
