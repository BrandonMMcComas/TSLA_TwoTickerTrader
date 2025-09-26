from __future__ import annotations

"""Deterministic decision engine for TSLA pair trading."""

import math
from dataclasses import dataclass
from typing import Dict, Optional

from app.config import settings as cfg
from app.core.runtime_state import state
from app.services import pricing
from app.services.live_vwap import vwap_distance_bps
from app.services.market_data import get_quote
from app.services.model import predict_p_up_latest

ReasonsDict = Dict[str, float | str | bool]


@dataclass
class DecisionInputs:
    interval: str
    last_sentiment_daily: Optional[float]
    session_pre: bool
    session_rth: bool
    session_after: bool


@dataclass
class DecisionResult:
    side: str
    conviction: float
    gate: float
    p_up: float
    p_sent: float
    p_blend: float
    spread_bps_tsll: float
    spread_bps_tsdd: float
    vwap_bps_tsla: Optional[float]
    reasons: ReasonsDict


def _normalize_weights(w_model: float, w_sent: float) -> tuple[float, float]:
    total = w_model + w_sent
    if total <= 0:
        return 1.0, 0.0
    return w_model / total, w_sent / total


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _hold_result(
    *,
    p_up: float,
    p_sent: float,
    p_blend: float,
    gate: float,
    spread_tsll: float,
    spread_tsdd: float,
    vwap_bps_tsla: Optional[float],
    reasons: ReasonsDict,
) -> DecisionResult:
    return DecisionResult(
        side="HOLD",
        conviction=0.0,
        gate=gate,
        p_up=p_up,
        p_sent=p_sent,
        p_blend=p_blend,
        spread_bps_tsll=spread_tsll,
        spread_bps_tsdd=spread_tsdd,
        vwap_bps_tsla=vwap_bps_tsla,
        reasons=reasons,
    )


def decide(inputs: DecisionInputs) -> DecisionResult:
    """Blend model and sentiment inputs into a deterministic trading decision."""

    reasons: ReasonsDict = {
        "session_pre": inputs.session_pre,
        "session_rth": inputs.session_rth,
        "session_after": inputs.session_after,
    }

    try:
        try:
            p_up_raw = float(predict_p_up_latest(inputs.interval))
        except Exception as exc:  # pragma: no cover - defensive logging only
            reasons["model_error"] = str(exc)
            p_up_raw = float("nan")

        p_up = p_up_raw if not math.isnan(p_up_raw) else 0.5

        if inputs.last_sentiment_daily is None or math.isnan(inputs.last_sentiment_daily):
            p_sent = 0.5
            reasons["sentiment_available"] = False
        else:
            p_sent = (float(inputs.last_sentiment_daily) + 1.0) / 2.0
            p_sent = _clamp(p_sent, 0.0, 1.0)
            reasons["sentiment_available"] = True

        w_model_norm, w_sent_norm = _normalize_weights(float(state.w_model), float(state.w_sent))
        p_blend = (w_model_norm * p_up) + (w_sent_norm * p_sent)

        reasons.update(
            {
                "w_model": w_model_norm,
                "w_sent": w_sent_norm,
                "p_up": p_up,
                "p_sent": p_sent,
                "p_blend": p_blend,
            }
        )

        try:
            q_tsll = get_quote(cfg.TSLL_SYMBOL)
            q_tsdd = get_quote(cfg.TSDD_SYMBOL)
            spread_tsll = pricing.spread_bps(q_tsll["bid"], q_tsll["ask"])
            spread_tsdd = pricing.spread_bps(q_tsdd["bid"], q_tsdd["ask"])
        except Exception as exc:  # pragma: no cover - defensive fallback
            reasons["quote_error"] = str(exc)
            spread_tsll = spread_tsdd = 999999.0

        for key, spread in (("spread_tsll", spread_tsll), ("spread_tsdd", spread_tsdd)):
            if not math.isfinite(spread) or spread < 0 or spread > 100_000:
                reasons[f"{key}_invalid"] = True
                spread_tsll = spread_tsdd = 999999.0
                break

        max_spread = max(spread_tsll, spread_tsdd)
        reasons["spread_bps_tsll"] = spread_tsll
        reasons["spread_bps_tsdd"] = spread_tsdd
        reasons["max_spread_bps"] = max_spread

        vwap_bps_tsla: Optional[float]
        if inputs.session_rth:
            try:
                vwap_bps_tsla = vwap_distance_bps(cfg.TSLA_SYMBOL)
            except Exception as exc:  # pragma: no cover - defensive fallback
                reasons["vwap_error"] = str(exc)
                vwap_bps_tsla = None
        else:
            vwap_bps_tsla = None

        reasons["vwap_bps_tsla"] = vwap_bps_tsla if vwap_bps_tsla is not None else "NA"

        base_gate = float(state.gate_threshold or cfg.GATE_THRESHOLD_DEFAULT)
        reasons["base_gate"] = base_gate
        gate = base_gate

        spread_block = float(getattr(state, "spread_max_bps", cfg.SPREAD_MAX_BPS))
        spread_hint = float(getattr(state, "spread_wide_hint", cfg.SPREAD_WIDE_BPS_HINT))
        gate_buffer = float(getattr(state, "gate_buffer_near_coinflip", cfg.GATE_BUFFER_NEAR_COINFLIP))

        if max_spread > spread_block:
            reasons["spread_block"] = True
            return _hold_result(
                p_up=p_up,
                p_sent=p_sent,
                p_blend=p_blend,
                gate=gate,
                spread_tsll=spread_tsll,
                spread_tsdd=spread_tsdd,
                vwap_bps_tsla=vwap_bps_tsla,
                reasons=reasons,
            )

        if max_spread > spread_hint:
            gate += cfg.GATE_ADJ_SPREAD_WIDE
            reasons["gate_adj_spread"] = cfg.GATE_ADJ_SPREAD_WIDE

        if inputs.session_pre or inputs.session_after:
            gate += cfg.GATE_ADJ_EXTENDED
            reasons["gate_adj_extended"] = cfg.GATE_ADJ_EXTENDED

        vwap_disagree = False
        if vwap_bps_tsla is not None:
            if p_blend >= 0.5 and vwap_bps_tsla < -cfg.VWAP_DISAGREE_BPS:
                gate += cfg.GATE_ADJ_EXTENDED
                reasons["gate_adj_vwap"] = cfg.GATE_ADJ_EXTENDED
                vwap_disagree = True
            elif p_blend < 0.5 and vwap_bps_tsla > cfg.VWAP_DISAGREE_BPS:
                gate += cfg.GATE_ADJ_EXTENDED
                reasons["gate_adj_vwap"] = cfg.GATE_ADJ_EXTENDED
                vwap_disagree = True

        gate = _clamp(gate, 0.45, 0.70)
        reasons["gate_after_adjustments"] = gate

        if abs(p_blend - 0.5) < gate_buffer:
            reasons["no_trade_buffer"] = True
            return _hold_result(
                p_up=p_up,
                p_sent=p_sent,
                p_blend=p_blend,
                gate=gate,
                spread_tsll=spread_tsll,
                spread_tsdd=spread_tsdd,
                vwap_bps_tsla=vwap_bps_tsla,
                reasons=reasons,
            )

        side = cfg.TSLL_SYMBOL if p_blend >= gate else cfg.TSDD_SYMBOL

        gate_distance = max(1e-6, abs(gate - 0.5))
        conviction = abs(p_blend - 0.5) / gate_distance
        conviction = _clamp(conviction, 0.0, 1.0)

        if vwap_disagree:
            conviction *= cfg.CONVICTION_DW_VWAP
            reasons["conviction_dw_vwap"] = cfg.CONVICTION_DW_VWAP

        if max_spread > spread_hint:
            conviction *= cfg.CONVICTION_DW_WIDE_SPREAD
            reasons["conviction_dw_spread"] = cfg.CONVICTION_DW_WIDE_SPREAD

        conviction = _clamp(conviction, 0.0, 1.0)

        return DecisionResult(
            side=side,
            conviction=conviction,
            gate=gate,
            p_up=p_up,
            p_sent=p_sent,
            p_blend=p_blend,
            spread_bps_tsll=spread_tsll,
            spread_bps_tsdd=spread_tsdd,
            vwap_bps_tsla=vwap_bps_tsla,
            reasons=reasons,
        )
    except Exception as exc:  # pragma: no cover - hard safety
        reasons["engine_error"] = str(exc)
        return _hold_result(
            p_up=0.5,
            p_sent=0.5,
            p_blend=0.5,
            gate=float(state.gate_threshold or cfg.GATE_THRESHOLD_DEFAULT),
            spread_tsll=999999.0,
            spread_tsdd=999999.0,
            vwap_bps_tsla=None,
            reasons=reasons,
        )
