from __future__ import annotations

"""Main window wiring sidebar navigation and page integration."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_config import AppConfig
from app.core.runtime_state import state
from app.core.usb_guard import read_keys_env
from app.gui.dashboard import Dashboard, DashboardMetrics
from app.gui.logs_panel import LogsPanel
from app.gui.settings_panel import SettingsPanel
from app.gui.trade_control import TradeControl
from app.gui.train_panel import TrainPanel
from app.gui.ui_state import UIState, load_ui_state


class MainWindow(QMainWindow):
    """Application shell with sidebar navigation and runtime status banner."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSLA Two-Ticker Trader — Decision Dashboard")
        self.resize(1280, 800)
        self.config = AppConfig.load()
        self.ui_state: UIState = load_ui_state()
        self._apply_state_defaults()

        self.banner_label = QLabel("Checking keys…")
        self.banner_label.setAlignment(Qt.AlignCenter)
        self.banner_label.setStyleSheet("font-weight:600; padding:8px; border-radius:6px;")

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self.banner_label)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setSpacing(4)
        self.sidebar.setAlternatingRowColors(False)
        self.sidebar.setStyleSheet(
            "QListWidget {background:#1f2933; color:white; border:none; padding:8px;}"
            "QListWidget::item {padding:10px; border-radius:6px;}"
            "QListWidget::item:selected {background:#2563eb;}"
        )

        self.stack = QStackedWidget()

        self.dashboard = Dashboard(self.config)
        self.trade = TradeControl(self.config)
        self.settings = SettingsPanel(self.config, self.ui_state, on_path_changed=self._on_usb_path_changed)
        self.logs = LogsPanel()
        self.train = TrainPanel()

        self.dashboard.decision_updated.connect(self._on_decision_updated)
        self.dashboard.show_logs_requested.connect(self._open_logs)
        self.settings.appearance_changed.connect(self._apply_appearance)
        self.settings.ui_state_synced.connect(self._on_ui_state_synced)

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.trade)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.logs)
        self.stack.addWidget(self.train)

        self._add_sidebar_item("Dashboard")
        self._add_sidebar_item("Trading")
        self._add_sidebar_item("Settings")
        self._add_sidebar_item("Logs")
        self._add_sidebar_item("Train")
        self.sidebar.setCurrentRow(0)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.stack, 1)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        self._install_shortcuts()
        self._apply_appearance(self.ui_state.dark_mode, self.ui_state.font_size)

        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self.refresh_keys_banner)
        self.timer.start()
        self.refresh_keys_banner()

    def _apply_state_defaults(self) -> None:
        state.gate_threshold = self.ui_state.gate_threshold
        state.w_model = self.ui_state.w_model
        state.w_sent = self.ui_state.w_sent
        setattr(state, "gate_buffer_near_coinflip", self.ui_state.gate_buffer)
        state.spread_max_bps = self.ui_state.spread_max_bps
        setattr(state, "spread_wide_hint", self.ui_state.spread_wide_hint)
        state.slippage_bps = self.ui_state.slippage_bps
        setattr(state, "flip_cooldown_sec", self.ui_state.flip_cooldown_sec)
        state.session_pre = self.ui_state.session_pre
        state.session_rth = self.ui_state.session_rth
        state.session_after = self.ui_state.session_after

    def _install_shortcuts(self) -> None:
        shortcuts = {
            "Ctrl+D": 0,
            "Ctrl+T": 1,
            "Ctrl+S": 2,
            "Ctrl+L": 3,
            "Ctrl+R": 4,
        }
        for key, index in shortcuts.items():
            shortcut = QShortcut(key, self)
            shortcut.activated.connect(lambda idx=index: self.sidebar.setCurrentRow(idx))

    def _apply_appearance(self, dark: bool, font_size: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if dark:
            palette = QPalette()
            palette.setColor(QPalette.Window, Qt.black)
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, Qt.black)
            palette.setColor(QPalette.AlternateBase, Qt.gray)
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.black)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, Qt.black)
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.Highlight, Qt.darkGray)
            palette.setColor(QPalette.HighlightedText, Qt.white)
            app.setPalette(palette)
        else:
            app.setPalette(app.style().standardPalette())

        sizes = {"Small": 9, "Normal": 10, "Large": 12}
        point_size = sizes.get(font_size, 10)
        font = QFont()
        font.setPointSize(point_size)
        app.setFont(font)

    def _add_sidebar_item(self, label: str) -> None:
        item = QListWidgetItem(label)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.sidebar.addItem(item)

    def _on_usb_path_changed(self, new_path: str) -> None:
        self.config.usb_keys_path = new_path
        self.config.save()
        self.refresh_keys_banner()

    def refresh_keys_banner(self) -> None:
        ok, masked = read_keys_env(self.config.usb_keys_path)
        if ok:
            details = "  ".join(f"{k}:{v}" for k, v in masked.items() if v)
            self.banner_label.setText(f"Keys present at {self.config.usb_keys_path} — {details}")
            self.banner_label.setStyleSheet(
                "background:#e6ffed; color:#05400A; border:1px solid #7fd18b; font-weight:600; padding:8px;"
            )
        else:
            self.banner_label.setText(f"No valid keys.env at {self.config.usb_keys_path}")
            self.banner_label.setStyleSheet(
                "background:#ffecec; color:#680000; border:1px solid #e0a0a0; font-weight:600; padding:8px;"
            )

    def _on_decision_updated(self, result, metrics: DashboardMetrics) -> None:
        self.trade.update_decision(result, metrics)

    def _open_logs(self, token: str) -> None:
        self.sidebar.setCurrentRow(3)
        self.logs.apply_filter_text(token)

    def _on_ui_state_synced(self, ui_state: UIState) -> None:
        self.ui_state = ui_state


def launch_gui() -> None:
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
