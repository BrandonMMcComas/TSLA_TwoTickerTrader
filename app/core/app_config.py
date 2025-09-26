from __future__ import annotations

from dataclasses import dataclass

from app.config.paths import APP_CONFIG_PATH
from app.config.settings import DEFAULT_USB_KEYS_PATH
from app.core.storage import read_json, write_json_atomic


@dataclass
class AppConfig:
    usb_keys_path: str = DEFAULT_USB_KEYS_PATH
    @staticmethod
    def load() -> "AppConfig":
        data = read_json(APP_CONFIG_PATH, default={}) or {}
        return AppConfig(usb_keys_path=data.get("usb_keys_path", DEFAULT_USB_KEYS_PATH))
    def save(self) -> None:
        write_json_atomic(APP_CONFIG_PATH, {"usb_keys_path": self.usb_keys_path})
