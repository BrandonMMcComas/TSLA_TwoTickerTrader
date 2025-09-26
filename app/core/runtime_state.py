from __future__ import annotations

from dataclasses import dataclass

from app.config import settings as cfg


@dataclass
class RuntimeState:
    gate_threshold: float = cfg.GATE_THRESHOLD_DEFAULT
    w_model: float = 0.70
    w_sent: float = 0.30
    gate_buffer_near_coinflip: float = cfg.GATE_BUFFER_NEAR_COINFLIP
    session_pre: bool = True
    session_rth: bool = True
    session_after: bool = False
    stop_loss_pct: float = 0.025
    slippage_bps: int = cfg.SLIPPAGE_BPS_DEFAULT if hasattr(cfg, "SLIPPAGE_BPS_DEFAULT") else 30
    spread_max_bps: int = cfg.SPREAD_MAX_BPS
    spread_wide_hint: int = cfg.SPREAD_WIDE_BPS_HINT
    stop_limit_offset_bps: int = 10
    flip_cooldown_sec: int = cfg.FLIP_COOLDOWN_SEC

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
