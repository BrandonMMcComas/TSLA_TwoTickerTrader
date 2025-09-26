from __future__ import annotations

"""Settings panel with runtime-aware sliders and appearance controls."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
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
from app.gui.ui_state import UIState, save_ui_state
from app.tools.create_shortcut import create_desktop_shortcut


class SettingsPanel(QWidget):
    """Organises decision engine, risk knobs, and appearance preferences."""

    appearance_changed = Signal(bool, str)
    ui_state_synced = Signal(UIState)

    def __init__(self, config: AppConfig, ui_state: UIState, on_path_changed=None) -> None:
        super().__init__()
        self.config = config
        self._ui_state = ui_state
        self._on_path_changed = on_path_changed
        self._block_weight_updates = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_usb_group())
        layout.addWidget(self._build_decision_group())
        layout.addWidget(self._build_risk_group())
        layout.addWidget(self._build_session_group())
        layout.addWidget(self._build_appearance_group())
        layout.addStretch(1)

    def _build_usb_group(self) -> QGroupBox:
        group = QGroupBox("USB Keys & Paths")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(self.config.usb_keys_path)
        browse = QPushButton("Browse…")
        save = QPushButton("Save Path")
        row.addWidget(self.path_edit)
        row.addWidget(browse)
        row.addWidget(save)
        layout.addLayout(row)

        layout.addWidget(QLabel("Keys remain on the USB; only the path is stored locally."))

        self.alpaca_id = QLineEdit()
        self.alpaca_id.setPlaceholderText("ALPACA_API_KEY_ID")
        self.alpaca_secret = QLineEdit()
        self.alpaca_secret.setPlaceholderText("ALPACA_API_SECRET_KEY")
        self.alpaca_secret.setEchoMode(QLineEdit.Password)
        self.openai_key = QLineEdit()
        self.openai_key.setPlaceholderText("OPENAI_API_KEY")
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.google_key = QLineEdit()
        self.google_key.setPlaceholderText("GOOGLE_API_KEY")
        self.google_key.setEchoMode(QLineEdit.Password)
        self.google_cse = QLineEdit()
        self.google_cse.setPlaceholderText("GOOGLE_CSE_ID")
        for widget in (
            self.alpaca_id,
            self.alpaca_secret,
            self.openai_key,
            self.google_key,
            self.google_cse,
        ):
            layout.addWidget(widget)
        save_keys = QPushButton("Save keys.env to USB")
        layout.addWidget(save_keys)

        shortcut_btn = QPushButton("Create Desktop Shortcut")
        layout.addWidget(shortcut_btn)

        browse.clicked.connect(self._browse)
        save.clicked.connect(self._save_path)
        save_keys.clicked.connect(self._save_keys)
        shortcut_btn.clicked.connect(self._make_shortcut)

        return group

    def _build_decision_group(self) -> QGroupBox:
        group = QGroupBox("Decision Engine")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        layout.addWidget(QLabel("Gate threshold"), 0, 0)
        self.slider_gate = QSlider(Qt.Horizontal)
        self.slider_gate.setRange(45, 70)
        self.slider_gate.setValue(int(self._ui_state.gate_threshold * 100))
        layout.addWidget(self.slider_gate, 0, 1)
        self.lbl_gate = QLabel(f"{self._ui_state.gate_threshold:.2f}")
        layout.addWidget(self.lbl_gate, 0, 2)

        layout.addWidget(QLabel("Model weight"), 1, 0)
        self.slider_model = QSlider(Qt.Horizontal)
        self.slider_model.setRange(0, 100)
        self.slider_model.setValue(int(self._ui_state.w_model * 100))
        layout.addWidget(self.slider_model, 1, 1)
        self.lbl_model = QLabel(f"{self._ui_state.w_model:.2f}")
        layout.addWidget(self.lbl_model, 1, 2)

        layout.addWidget(QLabel("Sentiment weight"), 2, 0)
        self.slider_sent = QSlider(Qt.Horizontal)
        self.slider_sent.setRange(0, 100)
        self.slider_sent.setValue(int(self._ui_state.w_sent * 100))
        layout.addWidget(self.slider_sent, 2, 1)
        self.lbl_sent = QLabel(f"{self._ui_state.w_sent:.2f}")
        layout.addWidget(self.lbl_sent, 2, 2)

        layout.addWidget(QLabel("Near-coinflip buffer (bps)"), 3, 0)
        self.slider_buffer = QSlider(Qt.Horizontal)
        self.slider_buffer.setRange(0, 5)
        self.slider_buffer.setValue(int(self._ui_state.gate_buffer * 100))
        layout.addWidget(self.slider_buffer, 3, 1)
        self.lbl_buffer = QLabel(f"{self._ui_state.gate_buffer:.2f}")
        layout.addWidget(self.lbl_buffer, 3, 2)

        self.slider_gate.valueChanged.connect(self._gate_changed)
        self.slider_model.valueChanged.connect(self._weights_changed)
        self.slider_sent.valueChanged.connect(self._weights_changed)
        self.slider_buffer.valueChanged.connect(self._buffer_changed)

        return group

    def _build_risk_group(self) -> QGroupBox:
        group = QGroupBox("Risk & Microstructure")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        layout.addWidget(QLabel("Spread max block (bps)"), 0, 0)
        self.spread_max = QSpinBox()
        self.spread_max.setRange(10, 500)
        self.spread_max.setValue(self._ui_state.spread_max_bps)
        layout.addWidget(self.spread_max, 0, 1)

        layout.addWidget(QLabel("Spread wide hint (bps)"), 1, 0)
        self.spread_hint = QSpinBox()
        self.spread_hint.setRange(10, 300)
        self.spread_hint.setValue(self._ui_state.spread_wide_hint)
        layout.addWidget(self.spread_hint, 1, 1)

        layout.addWidget(QLabel("Slippage (bps)"), 2, 0)
        self.slippage = QSpinBox()
        self.slippage.setRange(5, 200)
        self.slippage.setValue(self._ui_state.slippage_bps)
        layout.addWidget(self.slippage, 2, 1)

        layout.addWidget(QLabel("Flip cooldown (sec)"), 3, 0)
        self.flip_cooldown = QSpinBox()
        self.flip_cooldown.setRange(0, 600)
        self.flip_cooldown.setValue(self._ui_state.flip_cooldown_sec)
        layout.addWidget(self.flip_cooldown, 3, 1)

        self.spread_max.valueChanged.connect(self._risk_changed)
        self.spread_hint.valueChanged.connect(self._risk_changed)
        self.slippage.valueChanged.connect(self._risk_changed)
        self.flip_cooldown.valueChanged.connect(self._risk_changed)

        return group

    def _build_session_group(self) -> QGroupBox:
        group = QGroupBox("Sessions")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)
        self.chk_pre = QCheckBox("Pre")
        self.chk_rth = QCheckBox("RTH")
        self.chk_after = QCheckBox("After")
        self.chk_pre.setChecked(self._ui_state.session_pre)
        self.chk_rth.setChecked(self._ui_state.session_rth)
        self.chk_after.setChecked(self._ui_state.session_after)
        layout.addWidget(self.chk_pre)
        layout.addWidget(self.chk_rth)
        layout.addWidget(self.chk_after)
        layout.addStretch(1)

        self.chk_pre.stateChanged.connect(self._session_changed)
        self.chk_rth.stateChanged.connect(self._session_changed)
        self.chk_after.stateChanged.connect(self._session_changed)

        return group

    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)

        self.chk_dark = QCheckBox("Dark mode")
        self.chk_dark.setChecked(self._ui_state.dark_mode)
        layout.addWidget(self.chk_dark)

        layout.addWidget(QLabel("Font size"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Small", "Normal", "Large"])
        index = max(0, self.font_combo.findText(self._ui_state.font_size))
        self.font_combo.setCurrentIndex(index)
        layout.addWidget(self.font_combo)
        layout.addStretch(1)

        self.chk_dark.stateChanged.connect(self._appearance_changed)
        self.font_combo.currentTextChanged.connect(self._appearance_changed)

        return group

    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        directory = QFileDialog.getExistingDirectory(self, "Select USB Keys Folder", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)

    def _save_path(self) -> None:
        new_path = self.path_edit.text().strip()
        if not new_path or new_path == self.config.usb_keys_path:
            return
        self.config.usb_keys_path = new_path
        self.config.save()
        if self._on_path_changed:
            self._on_path_changed(new_path)

    def _save_keys(self) -> None:
        keys = {
            "ALPACA_API_KEY_ID": self.alpaca_id.text().strip(),
            "ALPACA_API_SECRET_KEY": self.alpaca_secret.text().strip(),
            "OPENAI_API_KEY": self.openai_key.text().strip(),
            "GOOGLE_API_KEY": self.google_key.text().strip(),
            "GOOGLE_CSE_ID": self.google_cse.text().strip(),
        }
        write_keys_env(self.config.usb_keys_path, keys)

    def _make_shortcut(self) -> None:
        try:
            target = os.path.abspath("start_app.cmd")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "TSLA Two-Ticker Trader.lnk")
            icon = str(ICONS_DIR / "tesla_coil.ico")
            create_desktop_shortcut(target, shortcut_path, icon)
        except Exception:
            return

    def _gate_changed(self, value: int) -> None:
        threshold = value / 100.0
        state.gate_threshold = threshold
        self._ui_state.gate_threshold = threshold
        self.lbl_gate.setText(f"{threshold:.2f}")
        self._persist()

    def _weights_changed(self, _: int) -> None:
        if self._block_weight_updates:
            return
        self._block_weight_updates = True
        model = self.slider_model.value()
        sent = self.slider_sent.value()
        if model + sent == 0:
            model = 70
            sent = 30
        if self.sender() == self.slider_model:
            sent = 100 - model
            self.slider_sent.setValue(sent)
        else:
            model = 100 - sent
            self.slider_model.setValue(model)
        self._block_weight_updates = False

        state.w_model = model / 100.0
        state.w_sent = sent / 100.0
        normalize_weights()
        self.slider_model.setValue(int(state.w_model * 100))
        self.slider_sent.setValue(int(state.w_sent * 100))
        self.lbl_model.setText(f"{state.w_model:.2f}")
        self.lbl_sent.setText(f"{state.w_sent:.2f}")
        self._ui_state.w_model = state.w_model
        self._ui_state.w_sent = state.w_sent
        self._persist()

    def _buffer_changed(self, value: int) -> None:
        buffer = value / 100.0
        self.lbl_buffer.setText(f"{buffer:.2f}")
        self._ui_state.gate_buffer = buffer
        setattr(state, "gate_buffer_near_coinflip", buffer)
        self._persist()

    def _risk_changed(self) -> None:
        state.spread_max_bps = self.spread_max.value()
        setattr(state, "spread_wide_hint", self.spread_hint.value())
        state.slippage_bps = self.slippage.value()
        setattr(state, "flip_cooldown_sec", self.flip_cooldown.value())
        self._ui_state.spread_max_bps = state.spread_max_bps
        self._ui_state.spread_wide_hint = getattr(state, "spread_wide_hint")
        self._ui_state.slippage_bps = state.slippage_bps
        self._ui_state.flip_cooldown_sec = getattr(state, "flip_cooldown_sec")
        self._persist()

    def _session_changed(self) -> None:
        state.session_pre = self.chk_pre.isChecked()
        state.session_rth = self.chk_rth.isChecked()
        state.session_after = self.chk_after.isChecked()
        self._ui_state.session_pre = state.session_pre
        self._ui_state.session_rth = state.session_rth
        self._ui_state.session_after = state.session_after
        self._persist()

    def _appearance_changed(self) -> None:
        self._ui_state.dark_mode = self.chk_dark.isChecked()
        self._ui_state.font_size = self.font_combo.currentText()
        self._persist()
        self.appearance_changed.emit(self._ui_state.dark_mode, self._ui_state.font_size)

    def _persist(self) -> None:
        save_ui_state(self._ui_state)
        self.ui_state_synced.emit(self._ui_state)
