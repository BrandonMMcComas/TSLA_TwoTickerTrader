from __future__ import annotations
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRectF

class Sparkline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.setMinimumHeight(28)

    def set_values(self, vals):
        self.values = list(vals)[-120:]  # cap
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        p.fillRect(rect, Qt.transparent)
        if not self.values:
            return
        lo = min(self.values); hi = max(self.values)
        if hi == lo:
            hi = lo + 1e-9
        n = len(self.values)
        step = rect.width() / max(1, n - 1)
        pen = QPen(QColor(60,60,60), 1.5)
        p.setPen(pen)
        for i in range(n - 1):
            x1 = rect.left() + i * step
            x2 = rect.left() + (i + 1) * step
            y1 = rect.bottom() - (self.values[i] - lo) / (hi - lo) * rect.height()
            y2 = rect.bottom() - (self.values[i+1] - lo) / (hi - lo) * rect.height()
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
