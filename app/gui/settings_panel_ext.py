from __future__ import annotations

"""
settings_panel_ext.py — adds a "Run sentiment now" button to the Settings panel
without touching the original file. We subclass and monkey-patch the exported
SettingsPanel symbol so the rest of the app uses the extended version.

UI:
- Mode: auto / am / pm
- Keep weekends: checkbox (default off)
- Button: "Run sentiment now"
- Status label: shows result and output path

Runs in a background QThread to avoid blocking the GUI.
"""

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Import the original SettingsPanel to subclass
from app.gui import settings_panel as sp


class _SentimentWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, mode: str, keep_weekends: bool):
        super().__init__()
        self.mode = mode
        self.keep_weekends = keep_weekends

    @Slot()
    def run(self):
        try:
            from app.tools.run_sentiment_once import run_once
            mode = "am" if self.mode.lower() == "am" else ("pm" if self.mode.lower() == "pm" else "am_or_pm_auto")
            # Map "auto" string to run_once signature
            rk = "am" if mode == "am" else ("pm" if mode == "pm" else ("am" if _is_am_now_et() else "pm"))
            p = run_once(rk, keep_weekends=self.keep_weekends)
            self.finished.emit(True, f"Sentiment {rk.upper()} complete → {p}")
        except SystemExit as e:
            # weekend skip or other controlled exits
            self.finished.emit(True, str(e))
        except Exception as e:
            self.finished.emit(False, f"{e}")

def _is_am_now_et() -> bool:
    try:
        import datetime

        import pytz
        NY = pytz.timezone("America/New_York")
        return datetime.datetime.now(NY).hour < 12
    except Exception:
        return True

class ExtendedSettingsPanel(sp.SettingsPanel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        root_layout = self.layout()
        if root_layout is None:
            return

        box = QGroupBox("Sentiment (Manual)")
        v = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mode:"))
        self._mode = QComboBox()
        self._mode.addItems(["auto", "am", "pm"])
        self._keep = QCheckBox("Keep weekends")
        self._btn = QPushButton("Run sentiment now")
        row.addWidget(self._mode)
        row.addStretch(1)
        row.addWidget(self._keep)
        row.addWidget(self._btn)
        v.addLayout(row)

        self._status = QLabel("Idle")
        v.addWidget(self._status)

        # Append to the bottom of existing Settings content
        try:
            root_layout.addWidget(box)
        except Exception:
            # If it's not a layout that supports addWidget, we silently ignore.
            pass

        self._btn.clicked.connect(self._on_click)

        # Thread/worker holders
        self._thr: Optional[QThread] = None
        self._worker: Optional[_SentimentWorker] = None

    def _on_click(self):
        mode = self._mode.currentText()
        keep = self._keep.isChecked()
        self._btn.setEnabled(False)
        self._status.setText("Running…")

        self._thr = QThread(self)
        self._worker = _SentimentWorker(mode, keep)
        self._worker.moveToThread(self._thr)
        self._thr.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.finished.connect(self._thr.quit)
        self._thr.start()

    @Slot(bool, str)
    def _on_done(self, ok: bool, msg: str):
        self._status.setText(("✅ " if ok else "⚠️ ") + msg)
        self._btn.setEnabled(True)

# Monkey-patch: replace the exported SettingsPanel with our extended version
setattr(sp, "SettingsPanel", ExtendedSettingsPanel)
