from __future__ import annotations

"""Structured log viewer with filters and decision-component highlighting."""

import csv
import datetime as dt
import json
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QDateTime, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.paths import DATA_DIR, LOGS_DIR

LOG_PATH = LOGS_DIR / "app.log"
TRADES_CSV = DATA_DIR / "trades.csv"


@dataclass
class LogsPayload:
    """Bundle of filtered log lines and recent trades."""

    lines: List[str]
    trades: List[str]


class LogsWorker(QObject):
    """Reads log and trade files in the background."""

    finished = Signal(LogsPayload)

    def __init__(self, since: Optional[dt.datetime]) -> None:
        super().__init__()
        self.since = since

    @Slot()
    def run(self) -> None:
        lines = _read_log_lines(self.since)
        trades = _read_trades()
        self.finished.emit(LogsPayload(lines=lines, trades=trades))


class LogsPanel(QWidget):
    """Filterable view of logs/app.log and data/trades.csv."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._filters_changed = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Level"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        filter_row.addWidget(self.level_combo)

        filter_row.addWidget(QLabel("Contains"))
        self.contains_edit = QLineEdit()
        filter_row.addWidget(self.contains_edit)

        filter_row.addWidget(QLabel("Since"))
        self.since_widget = QDateTimeEditExtended()
        filter_row.addWidget(self.since_widget)

        self.btn_clear = QPushButton("Clear")
        self.btn_export = QPushButton("Export…")
        filter_row.addWidget(self.btn_clear)
        filter_row.addWidget(self.btn_export)
        filter_row.addStretch(1)

        layout.addLayout(filter_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(8000)
        self.log_view.setStyleSheet("font-family: 'Fira Code', 'Consolas', monospace; font-size:10pt;")
        layout.addWidget(self.log_view)

        self.status_label = QLabel("Logs refresh every 2s. Filters apply live.")
        self.status_label.setStyleSheet("color:#666666;")
        layout.addWidget(self.status_label)

        self.level_combo.currentTextChanged.connect(self._on_filters_changed)
        self.contains_edit.textChanged.connect(self._on_filters_changed)
        self.since_widget.dateTimeChanged.connect(self._on_filters_changed)
        self.btn_clear.clicked.connect(self._clear_filters)
        self.btn_export.clicked.connect(self._export)

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()
        self._refresh()

    def apply_filter_text(self, text: str) -> None:
        self.contains_edit.setText(text)
        self._on_filters_changed()

    def _on_filters_changed(self) -> None:
        self._filters_changed = True
        self._refresh()

    def _clear_filters(self) -> None:
        self.level_combo.setCurrentIndex(0)
        self.contains_edit.clear()
        self.since_widget.reset()
        self._on_filters_changed()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Logs", str(DATA_DIR / "logs_export.txt"))
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.log_view.toPlainText())

    def _refresh(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        since_dt = self.since_widget.dateTime().toPython()
        thread = QThread(self)
        worker = LogsWorker(since_dt)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_payload)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    @Slot(LogsPayload)
    def _on_payload(self, payload: LogsPayload) -> None:
        level = self.level_combo.currentText()
        text_filter = self.contains_edit.text().strip().lower()
        filtered: List[str] = []
        for line in payload.lines:
            if level != "ALL" and f"[{level}]" not in line:
                continue
            if text_filter and text_filter not in line.lower():
                continue
            filtered.append(_format_line(line))
        if payload.trades:
            filtered.append("\n--- recent trades ---")
            for trade in payload.trades:
                if text_filter and text_filter not in trade.lower():
                    continue
                filtered.append(trade)
        self.log_view.setPlainText("\n".join(filtered))

    def focus_on_token(self, token: str) -> None:
        self.apply_filter_text(token)


class QDateTimeEditExtended(QDateTimeEdit):
    """Date-time selector defaulting to one hour look-back."""

    def __init__(self) -> None:
        super().__init__(QDateTime.currentDateTime().addSecs(-3600))
        self.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.setCalendarPopup(True)

    def reset(self) -> None:
        self.setDateTime(QDateTime.currentDateTime().addSecs(-3600))


def _read_log_lines(since: Optional[dt.datetime]) -> List[str]:
    if not LOG_PATH.exists():
        return []
    try:
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-4000:]
    except OSError:
        return []
    if not since:
        return [line.rstrip() for line in lines]
    filtered = []
    for line in lines:
        parsed = _parse_log_time(line)
        if parsed and parsed < since:
            continue
        filtered.append(line.rstrip())
    return filtered


def _read_trades(max_rows: int = 50) -> List[str]:
    if not TRADES_CSV.exists():
        return []
    rows = []
    try:
        with TRADES_CSV.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(row)
    except (OSError, csv.Error):
        return []
    rows = rows[-max_rows:]
    formatted: List[str] = []
    for row in rows:
        ts = row.get("ts", "?")
        action = row.get("action", "?")
        symbol = row.get("symbol", "?")
        qty = row.get("qty", "?")
        price = row.get("price", row.get("px", "?"))
        components_raw = row.get("decision_components_json")
        decision_text = _format_decision_components(components_raw)
        formatted.append(f"{ts} | {action} {symbol} x{qty} @ {price}{decision_text}")
    return formatted


def _format_decision_components(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return f" | components: {raw}"
    items = [f"{key}={value}" for key, value in data.items() if key not in {"reasons"}]
    if "reasons" in data and isinstance(data["reasons"], dict):
        reasons = ", ".join(f"{k}:{v}" for k, v in data["reasons"].items())
        items.append(f"reasons=[{reasons}]")
    return " | " + ", ".join(items)


def _parse_log_time(line: str) -> Optional[dt.datetime]:
    try:
        prefix = line[:19]
        return dt.datetime.strptime(prefix, "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return None


def _format_line(line: str) -> str:
    if "decision_components_json" in line:
        try:
            prefix, json_blob = line.split("decision_components_json=", 1)
            decision_text = _format_decision_components(json_blob.strip())
            return f"{prefix.strip()} {decision_text}"
        except ValueError:
            return line
    return line
