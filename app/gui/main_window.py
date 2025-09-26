from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_config import AppConfig
from app.core.usb_guard import read_keys_env
from app.gui.dashboard import Dashboard
from app.gui.logs_panel import LogsPanel
from app.gui.settings_panel import SettingsPanel
from app.gui.trade_control import TradeControl
from app.gui.train_panel import TrainPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSLA Two-Ticker Trader — Section 03")
        self.resize(1150, 760)
        self.config = AppConfig.load()
        self.banner_label = QLabel("Checking keys…")
        self.banner_label.setAlignment(Qt.AlignCenter)
        self.banner_label.setStyleSheet("font-weight: 600; padding: 8px;")
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)
        v.addWidget(self.banner_label)
        tabs = QTabWidget()
        self.dashboard = Dashboard(self.config)
        self.train = TrainPanel()
        self.trade_control = TradeControl(self.config)
        self.settings = SettingsPanel(
            self.config, on_path_changed=self._on_usb_path_changed
        )
        self.logs = LogsPanel()
        tabs.addTab(self.dashboard, "Dashboard")
        tabs.addTab(self.train, "Train (Model)")
        tabs.addTab(self.trade_control, "Trade Control")
        tabs.addTab(self.settings, "Settings")
        tabs.addTab(self.logs, "Logs")
        v.addWidget(tabs)
        self.setCentralWidget(root)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_keys_banner)
        self.timer.start(2000)
        self.refresh_keys_banner()

    def _on_usb_path_changed(self, new_path: str):
        self.config.usb_keys_path = new_path
        self.config.save()
        self.refresh_keys_banner()

    def refresh_keys_banner(self):
        ok, masked = read_keys_env(self.config.usb_keys_path)
        if ok:
            self.banner_label.setText(
                f"Keys present at {self.config.usb_keys_path}  —  "
                + "  ".join(f"{k}:{v}" for k, v in masked.items() if v)
            )
            self.banner_label.setStyleSheet(
                (
                    "background:#e6ffed; color:#05400A; border:1px solid #7fd18b; "
                    "font-weight:600; padding:8px;"
                )
            )
        else:
            self.banner_label.setText(
                (
                    f"No valid keys.env at {self.config.usb_keys_path} — "
                    "create D:\\SWINGBOT_KEYS\\keys.env"
                )
            )
            self.banner_label.setStyleSheet(
                (
                    "background:#ffecec; color:#680000; border:1px solid #e0a0a0; "
                    "font-weight:600; padding:8px;"
                )
            )


def launch_gui():
    import sys

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
