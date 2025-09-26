"""
app.services.telegram — minimal Telegram Bot API helper (no extra deps)
- Sends messages using HTTPS to api.telegram.org
- Reads token/chat_id from USB keys.env via usb_guard.get_keys_dict
"""

from __future__ import annotations

from typing import Optional

import requests

from app.core.app_config import AppConfig
from app.core.usb_guard import get_keys_dict

TELEGRAM_TOKEN_KEY = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_KEY = "TELEGRAM_CHAT_ID"


class TelegramNotifier:
    def __init__(self, token: Optional[str], chat_id: Optional[str]):
        self.token = token or ""
        self.chat_id = chat_id or ""

    @classmethod
    def from_usb(cls) -> "TelegramNotifier":
        cfg = AppConfig.load()
        kv = get_keys_dict(cfg.usb_keys_path)
        return cls(kv.get(TELEGRAM_TOKEN_KEY, ""), kv.get(TELEGRAM_CHAT_ID_KEY, ""))

    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str, parse_mode: Optional[str] = None) -> bool:
        if not self.configured():
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            r = requests.post(url, json=payload, timeout=10)
            return r.ok
        except Exception:
            return False

    def detect_chat_id(self) -> Optional[str]:
        """Try to fetch the most recent chat_id from getUpdates.
        Ask the user to send any message to the bot first."""
        if not self.token:
            return None
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            r = requests.get(url, timeout=10)
            if not r.ok:
                return None
            js = r.json()
            # Take the most recent update's chat id
            for upd in reversed(js.get("result", [])):
                try:
                    chat = upd.get("message", {}).get("chat", {})
                    cid = chat.get("id")
                    if cid:
                        return str(cid)
                except Exception:
                    continue
        except Exception:
            return None
        return None


def format_account_snapshot() -> str:
    """Fetch a simple Alpaca account + positions snapshot and format for Telegram.
    Loads keys from USB automatically. Returns a human-readable string.
    """
    from alpaca.trading.client import TradingClient

    from app.config.settings import APP_NAME
    from app.core.app_config import AppConfig
    from app.core.usb_guard import load_keys_from_usb

    cfg = AppConfig.load()
    if not load_keys_from_usb(cfg.usb_keys_path):
        return f"{APP_NAME}: Unable to load Alpaca keys from USB."

    client = TradingClient(api_key=None, secret_key=None, paper=False)  # keys from env
    acct = client.get_account()

    lines = []
    lines.append(f"{APP_NAME} — Account Snapshot")
    lines.append(f"Status: {acct.status}")
    lines.append(f"Equity: ${acct.equity}")
    lines.append(f"Cash: ${acct.cash}")
    try:
        lines.append(f"NMBP: ${acct.non_marginable_buying_power}")
    except Exception:
        pass
    try:
        lines.append(f"Daytrade count (5d): {acct.daytrade_count}")
    except Exception:
        pass
    lines.append("Positions:")
    try:
        positions = client.get_all_positions()
        if not positions:
            lines.append("  (none)")
        else:
            for p in positions:
                lines.append(f"  {p.symbol}: {p.qty} @ ${p.avg_entry_price}")
    except Exception:
        lines.append("  (error reading positions)")

    return "\n".join(lines)
