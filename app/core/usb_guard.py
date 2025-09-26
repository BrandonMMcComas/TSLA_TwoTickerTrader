from __future__ import annotations

main
"""
usb_guard.py — Hotfix v1.4.4

- `read_keys_env(path)` returns (ok: bool, masked_dict: dict[str,str])
  (matches GUI expectation: `ok, masked = read_keys_env(...); masked.items()`)
- `get_keys_dict(path)` returns raw dict (no loading into env).
- `write_keys_env`, `load_keys_from_usb`, `keys_present` unchanged.
- Secrets remain USB-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from dotenv import dotenv_values, load_dotenv

from app.config.settings import (
    DEFAULT_KEYS_USB_PATH,
    DEFAULT_USB_KEYS_PATH,
    KEYS_ENV_FILENAME,
)

from app.config.settings import DEFAULT_KEYS_USB_PATH, DEFAULT_USB_KEYS_PATH, KEYS_ENV_FILENAME
main

USB_DEFAULT = DEFAULT_USB_KEYS_PATH
USB_DEFAULT_ALIAS = DEFAULT_KEYS_USB_PATH  # legacy alias


def _keys_file(path: Optional[str] = None) -> Path:
    base = Path(path or USB_DEFAULT)
    return base / KEYS_ENV_FILENAME


def _mask_tail(val: str, tail: int = 4) -> str:
    if not val:
        return "(missing)"
    s = str(val)
    return f"••••{s[-tail:]}" if len(s) >= tail else "••••"


def get_keys_dict(path: Optional[str] = None) -> Dict[str, str]:
    p = _keys_file(path)
    if not p.exists():
        return {}
    return dotenv_values(p) or {}


def read_keys_env(path: Optional[str] = None) -> Tuple[bool, Dict[str, str]]:
    kv = get_keys_dict(path)
    masked: Dict[str, str] = {}
    if not kv:
        return False, masked

    masked["Alpaca ID"] = _mask_tail(kv.get("ALPACA_API_KEY_ID", ""))
    masked["Alpaca Secret"] = _mask_tail(kv.get("ALPACA_API_SECRET_KEY", ""))
    if kv.get("OPENAI_API_KEY"):
        masked["OpenAI"] = _mask_tail(kv.get("OPENAI_API_KEY", ""))
    if kv.get("GOOGLE_API_KEY"):
        masked["Google"] = _mask_tail(kv.get("GOOGLE_API_KEY", ""))
    if kv.get("GOOGLE_CSE_ID"):
        masked["CSE"] = _mask_tail(kv.get("GOOGLE_CSE_ID", ""))

    ok = bool(kv.get("ALPACA_API_KEY_ID") and kv.get("ALPACA_API_SECRET_KEY"))
    return ok, masked


def write_keys_env(path: Optional[str], kv: Dict[str, str]) -> bool:
    if not path:
        path = USB_DEFAULT
    p = _keys_file(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    existing = get_keys_dict(path)
    merged = dict(existing)
    for k, v in (kv or {}).items():
        if v is not None and str(v).strip() != "":
            merged[k] = str(v).strip()

    lines = []
    for k in (
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CSE_ID",
    ):
        if k in merged:
            lines.append(f"{k}={merged[k]}\n")
    p.write_text("".join(lines), encoding="utf-8")
    return True


def load_keys_from_usb(path: Optional[str] = None) -> bool:
    p = _keys_file(path)
    if not p.exists():
        return False
    load_dotenv(p, override=True)
    return True


def keys_present(path: Optional[str] = None) -> bool:
    kv = get_keys_dict(path)
    return bool(kv.get("ALPACA_API_KEY_ID") and kv.get("ALPACA_API_SECRET_KEY"))
