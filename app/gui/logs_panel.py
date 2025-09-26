from __future__ import annotations
"""
logs_panel.py — Hotfix v1.4.5

Fixes:
- PySide6 enum scoping: QTextCursor.End -> QTextCursor.MoveOperation.End
- Adds safe tailing of logs/app.log and data/trades.csv with "Open folder" buttons.

This panel shows:
- Live tail of logs/app.log
- Simple table view of data/trades.csv (if present)
"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QHBoxLayout, QPlainTextEdit, QTableWidget, QTableWidgetItem
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QTextCursor
from app.config.paths import LOGS_DIR, DATA_DIR

LOG_PATH = LOGS_DIR / "app.log"
TRADES_CSV = DATA_DIR / "trades.csv"

class LogsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        v = QVBoxLayout(self)

        # Header row with open-folder buttons
        row = QHBoxLayout()
        row.addWidget(QLabel("<b>Logs</b>"))
        btn_open_logs = QPushButton("Open logs folder")
        btn_open_data = QPushButton("Open data folder")
        row.addStretch(1); row.addWidget(btn_open_logs); row.addWidget(btn_open_data)
        v.addLayout(row)

        # Log tail view
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)  # auto-prune
        v.addWidget(self.log_view, 2)

        # Trades table (very simple)
        self.tbl = QTableWidget(self)
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["ts","action","symbol","qty","px","note"])
        v.addWidget(self.tbl, 1)

        # Wire
        btn_open_logs.clicked.connect(lambda: self._open_folder(LOGS_DIR))
        btn_open_data.clicked.connect(lambda: self._open_folder(DATA_DIR))

        # Timer to refresh tail & table
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(1500)
        self._tick()

    def _open_folder(self, path):
        try:
            os.startfile(str(path))
        except Exception:
            pass

    def _tail_log(self, max_bytes: int = 200_000) -> str:
        p = LOG_PATH
        if not p.exists():
            return "(no app.log yet)"
        try:
            size = p.stat().st_size
            with open(p, "rb") as f:
                if size > max_bytes:
                    f.seek(-max_bytes, os.SEEK_END)
                data = f.read()
            # try utf-8, fallback
            try:
                return data.decode("utf-8", errors="replace")
            except Exception:
                return data.decode(errors="replace")
        except Exception as e:
            return f"Error reading log: {e}"

    def _load_trades(self, max_rows: int = 200):
        p = TRADES_CSV
        if not p.exists():
            self.tbl.setRowCount(0)
            return
        try:
            rows = []
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i == 0 and "ts,action" in line:  # header skip
                        continue
                    parts = [s.strip() for s in line.strip().split(",")]
                    rows.append(parts[:6])  # take first 6 cols
            rows = rows[-max_rows:]
            self.tbl.setRowCount(len(rows))
            for r, parts in enumerate(rows):
                for c in range(6):
                    val = parts[c] if c < len(parts) else ""
                    self.tbl.setItem(r, c, QTableWidgetItem(val))
        except Exception:
            # soft-fail on csv parse
            self.tbl.setRowCount(0)

    def _tick(self):
        # tail logs
        text = self._tail_log()
        self.log_view.setPlainText(text)
        # move cursor to end using PySide6 enum scoping
        try:
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        except Exception:
            # last resort: select all then move to end
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)

        # trades table
        self._load_trades()
