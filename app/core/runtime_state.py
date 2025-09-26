from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeState:
    gate_threshold: float = 0.55
    w_model: float = 0.70
    w_sent: float = 0.30
    session_pre: bool = True
    session_rth: bool = True
    session_after: bool = False
    stop_loss_pct: float = 0.025
    slippage_bps: int = 30
    spread_max_bps: int = 75
    stop_limit_offset_bps: int = 10

    # engine wiring
    engine_running: bool = False
    interval: str = "5m"  # for model p_up polling
    lookback_days: int = 30


state = RuntimeState()


def normalize_weights():
    s = state.w_model + state.w_sent
    if s <= 0:
        state.w_model, state.w_sent = 0.70, 0.30
        return
    state.w_model /= s
    state.w_sent /= s
