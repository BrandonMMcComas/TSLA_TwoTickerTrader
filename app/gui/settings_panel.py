from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config.paths import ICONS_DIR
from app.core.app_config import AppConfig
from app.core.runtime_state import normalize_weights, state
from app.core.usb_guard import write_keys_env
from app.tools.create_shortcut import create_desktop_shortcut


class SettingsPanel(QWidget):
    def __init__(self, config: AppConfig, on_path_changed=None) -> None:
        super().__init__()
        self.config = config
        self._on_path_changed = on_path_changed
        v = QVBoxLayout(self)

        # USB path
        v.addWidget(QLabel("<b>USB Keys Path</b>"))
        row = QHBoxLayout()
        self.path_edit = QLineEdit(self.config.usb_keys_path)
        browse = QPushButton("Browse…")
        save_path = QPushButton("Save Path")
        row.addWidget(self.path_edit); row.addWidget(browse); row.addWidget(save_path)
        v.addLayout(row)
        v.addWidget(QLabel("Only the USB path is stored locally in data/app_config.json. No secrets are written to local disk."))

        # Keys writer
        v.addSpacing(10); v.addWidget(QLabel("<b>API Keys (saved to USB only)</b>"))
        self.alpaca_id = QLineEdit(); self.alpaca_id.setPlaceholderText("ALPACA_API_KEY_ID")
        self.alpaca_secret = QLineEdit(); self.alpaca_secret.setPlaceholderText("ALPACA_API_SECRET_KEY"); self.alpaca_secret.setEchoMode(QLineEdit.Password)
        self.openai_key = QLineEdit(); self.openai_key.setPlaceholderText("OPENAI_API_KEY"); self.openai_key.setEchoMode(QLineEdit.Password)
        self.google_key = QLineEdit(); self.google_key.setPlaceholderText("GOOGLE_API_KEY"); self.google_key.setEchoMode(QLineEdit.Password)
        self.google_cse = QLineEdit(); self.google_cse.setPlaceholderText("GOOGLE_CSE_ID")
        for w in [self.alpaca_id, self.alpaca_secret, self.openai_key, self.google_key, self.google_cse]:
            v.addWidget(w)
        save_keys_btn = QPushButton("Save keys.env to USB")
        v.addWidget(save_keys_btn)

        # Gate threshold & blend weights
        v.addSpacing(10); v.addWidget(QLabel("<b>Trade Gate & Sentiment Blend</b>"))
        rowt = QHBoxLayout()
        rowt.addWidget(QLabel("Gate threshold (0.40–0.70):"))
        self.thresh = QSlider(Qt.Horizontal); self.thresh.setMinimum(40); self.thresh.setMaximum(70); self.thresh.setValue(int(state.gate_threshold*100))
        self.lbl_thresh = QLabel(f"{state.gate_threshold:.2f}")
        rowt.addWidget(self.thresh); rowt.addWidget(self.lbl_thresh)
        v.addLayout(rowt)

        roww = QHBoxLayout()
        roww.addWidget(QLabel("w_model:"))
        self.wm = QSlider(Qt.Horizontal); self.wm.setMinimum(0); self.wm.setMaximum(100); self.wm.setValue(int(state.w_model*100))
        roww.addWidget(self.wm)
        roww.addWidget(QLabel("w_sent:"))
        self.ws = QSlider(Qt.Horizontal); self.ws.setMinimum(0); self.ws.setMaximum(100); self.ws.setValue(int(state.w_sent*100))
        roww.addWidget(self.ws)
        norm = QPushButton("Normalize weights")
        roww.addWidget(norm)
        v.addLayout(roww)

        # Sessions
        v.addSpacing(10); v.addWidget(QLabel("<b>Sessions</b>"))
        self.chk_pre = QCheckBox("Pre (04:00–09:30)"); self.chk_pre.setChecked(state.session_pre)
        self.chk_rth = QCheckBox("RTH (09:30–16:00)"); self.chk_rth.setChecked(state.session_rth)
        self.chk_after = QCheckBox("After (16:00–20:00)"); self.chk_after.setChecked(state.session_after)
        v.addWidget(self.chk_pre); v.addWidget(self.chk_rth); v.addWidget(self.chk_after)

        # Risk/price controls
        v.addSpacing(10); v.addWidget(QLabel("<b>Risk & Pricing</b>"))
        self.sl_stop = QSlider(Qt.Horizontal); self.sl_stop.setMinimum(10); self.sl_stop.setMaximum(500); self.sl_stop.setValue(int(state.stop_loss_pct*10000))  # 1.0%..5.0%
        self.lbl_stop = QLabel(f"Stop-loss: {state.stop_loss_pct*100:.2f}%")
        v.addWidget(self.lbl_stop); v.addWidget(self.sl_stop)

        self.sp_slip = QSpinBox(); self.sp_slip.setRange(5, 200); self.sp_slip.setValue(state.slippage_bps)
        self.sp_spread = QSpinBox(); self.sp_spread.setRange(10, 300); self.sp_spread.setValue(state.spread_max_bps)
        self.sp_stoplim = QSpinBox(); self.sp_stoplim.setRange(5, 100); self.sp_stoplim.setValue(state.stop_limit_offset_bps)
        rowr = QHBoxLayout()
        rowr.addWidget(QLabel("Slippage (bps):")); rowr.addWidget(self.sp_slip)
        rowr.addWidget(QLabel("Spread max (bps):")); rowr.addWidget(self.sp_spread)
        rowr.addWidget(QLabel("Stop-limit offset (bps):")); rowr.addWidget(self.sp_stoplim)
        v.addLayout(rowr)

        # Shortcut
        v.addSpacing(10); v.addWidget(QLabel("<b>Windows Desktop Shortcut</b>"))
        self.btn_shortcut = QPushButton("Create Desktop Shortcut")
        v.addWidget(self.btn_shortcut)

        # Wire up
        browse.clicked.connect(self._browse)
        save_path.clicked.connect(self._save_path)
        save_keys_btn.clicked.connect(self._save_keys)
        self.thresh.valueChanged.connect(self._thr_change)
        self.wm.valueChanged.connect(self._w_change)
        self.ws.valueChanged.connect(self._w_change)
        norm.clicked.connect(self._normalize)
        self.chk_pre.stateChanged.connect(self._sess_change)
        self.chk_rth.stateChanged.connect(self._sess_change)
        self.chk_after.stateChanged.connect(self._sess_change)
        self.sl_stop.valueChanged.connect(self._stop_change)
        self.sp_slip.valueChanged.connect(self._risk_change)
        self.sp_spread.valueChanged.connect(self._risk_change)
        self.sp_stoplim.valueChanged.connect(self._risk_change)
        self.btn_shortcut.clicked.connect(self._make_shortcut)

        v.addStretch(1)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select USB Keys Folder", self.path_edit.text())
        if d: self.path_edit.setText(d)

    def _save_path(self):
        new_path = self.path_edit.text().strip()
        if new_path and new_path != self.config.usb_keys_path:
            self.config.usb_keys_path = new_path; self.config.save()
            if self._on_path_changed: self._on_path_changed(new_path)

    def _save_keys(self):
        keys = {
            "ALPACA_API_KEY_ID": self.alpaca_id.text().strip(),
            "ALPACA_API_SECRET_KEY": self.alpaca_secret.text().strip(),
            "OPENAI_API_KEY": self.openai_key.text().strip(),
            "GOOGLE_API_KEY": self.google_key.text().strip(),
            "GOOGLE_CSE_ID": self.google_cse.text().strip(),
        }
        write_keys_env(self.config.usb_keys_path, keys)

    def _thr_change(self, val: int):
        state.gate_threshold = val / 100.0
        self.lbl_thresh.setText(f"{state.gate_threshold:.2f}")

    def _w_change(self, _):
        state.w_model = self.wm.value()/100.0
        state.w_sent = self.ws.value()/100.0

    def _normalize(self):
        normalize_weights()
        self.wm.setValue(int(state.w_model*100))
        self.ws.setValue(int(state.w_sent*100))

    def _sess_change(self, _):
        state.session_pre = self.chk_pre.isChecked()
        state.session_rth = self.chk_rth.isChecked()
        state.session_after = self.chk_after.isChecked()

    def _stop_change(self, val: int):
        state.stop_loss_pct = val/10000.0
        self.lbl_stop.setText(f"Stop-loss: {state.stop_loss_pct*100:.2f}%")

    def _risk_change(self, _):
        state.slippage_bps = self.sp_slip.value()
        state.spread_max_bps = self.sp_spread.value()
        state.stop_limit_offset_bps = self.sp_stoplim.value()

    def _make_shortcut(self):
        try:
            target = os.path.abspath("start_app.cmd")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "TSLA Two-Ticker Trader.lnk")
            icon = str(ICONS_DIR / "tesla_coil.ico")
            create_desktop_shortcut(target, shortcut_path, icon)
        except Exception:
            # Soft failure; avoid crashing Settings UI
            pass
