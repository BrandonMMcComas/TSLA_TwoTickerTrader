from __future__ import annotations

"""Helpers for persisting lightweight GUI preferences to ``data/ui_state.json``."""

import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict

from app.config.paths import DATA_DIR
from app.core.runtime_state import state


@dataclass
class UIState:
    """Serializable container for persisted GUI preferences and runtime knobs."""

    gate_threshold: float = state.gate_threshold
    w_model: float = state.w_model
    w_sent: float = state.w_sent
    gate_buffer: float = 0.03
    spread_max_bps: int = state.spread_max_bps
    spread_wide_hint: int = 50
    slippage_bps: int = state.slippage_bps
    flip_cooldown_sec: int = 60
    session_pre: bool = state.session_pre
    session_rth: bool = state.session_rth
    session_after: bool = state.session_after
    dark_mode: bool = False
    font_size: str = "Normal"  # Small | Normal | Large


_UI_STATE_PATH = DATA_DIR / "ui_state.json"


def load_ui_state() -> UIState:
    """Return persisted :class:`UIState`, falling back to defaults on error."""

    path = _UI_STATE_PATH
    if not path.exists():
        return UIState()

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload: Dict[str, Any] = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return UIState()

    state_kwargs: Dict[str, Any] = {}
    for field in fields(UIState):
        if field.name in payload:
            state_kwargs[field.name] = payload[field.name]

    return UIState(**state_kwargs)


def save_ui_state(ui_state: UIState) -> None:
    """Persist ``ui_state`` to ``data/ui_state.json`` in a defensive manner."""

    path = _UI_STATE_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(ui_state), handle, indent=2, sort_keys=True)
    except OSError:
        # Persistence is best-effort; ignore disk errors to avoid crashing the GUI.
        return
