from __future__ import annotations

import math
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

for _mod in ("numpy", "pandas", "yfinance", "pytz"):
    if _mod not in sys.modules:
        stub = ModuleType(_mod)
        if _mod == "numpy":
            setattr(stub, "nan", float("nan"))
        if _mod == "pytz":
            setattr(stub, "timezone", lambda _name: None)
        sys.modules[_mod] = stub

model_stub = ModuleType("app.services.model")
model_stub.predict_p_up_latest = lambda _interval: 0.5
sys.modules.setdefault("app.services.model", model_stub)

from app.config import settings
from app.core.runtime_state import state
from app.services import decision_engine
from app.services.decision_engine import DecisionInputs, decide


@pytest.fixture(autouse=True)
def _reset_runtime_state(monkeypatch):
    monkeypatch.setattr(state, "gate_threshold", settings.GATE_THRESHOLD_DEFAULT, raising=False)
    monkeypatch.setattr(state, "w_model", settings.BLEND_W_MODEL, raising=False)
    monkeypatch.setattr(state, "w_sent", settings.BLEND_W_SENT, raising=False)


def _patch_quotes(monkeypatch, bid: float, ask: float, last: float = math.nan):
    last_price = last if not math.isnan(last) else (bid + ask) / 2.0

    def _fake_quote(symbol: str):
        return {"symbol": symbol, "bid": bid, "ask": ask, "last": last_price, "ts": None}

    monkeypatch.setattr(decision_engine, "get_quote", _fake_quote)


def test_decision_balanced_long_tilt(monkeypatch):
    """Narrow spread with a modest long edge selects TSLL when buffer allows."""

    monkeypatch.setattr(decision_engine.cfg, "GATE_BUFFER_NEAR_COINFLIP", 0.01)
    monkeypatch.setattr(state, "gate_threshold", 0.52, raising=False)
    monkeypatch.setattr(state, "w_model", 1.0, raising=False)
    monkeypatch.setattr(state, "w_sent", 0.0, raising=False)
    monkeypatch.setattr(decision_engine, "predict_p_up_latest", lambda interval: 0.52)
    monkeypatch.setattr(decision_engine, "vwap_distance_bps", lambda symbol: 0.0)
    _patch_quotes(monkeypatch, bid=10.0, ask=10.01)

    inputs = DecisionInputs(
        interval="5m",
        last_sentiment_daily=None,
        session_pre=False,
        session_rth=True,
        session_after=False,
    )

    result = decide(inputs)

    assert result.side == settings.TSLL_SYMBOL
    assert 0.0 < result.conviction <= 1.0
    assert result.reasons["sentiment_available"] is False


def test_decision_blocks_wide_spread(monkeypatch):
    """Extremely wide spreads trigger a hold via spread_block."""

    monkeypatch.setattr(decision_engine, "predict_p_up_latest", lambda interval: 0.8)
    monkeypatch.setattr(decision_engine, "vwap_distance_bps", lambda symbol: 0.0)
    _patch_quotes(monkeypatch, bid=10.0, ask=10.08)

    inputs = DecisionInputs(
        interval="5m",
        last_sentiment_daily=0.0,
        session_pre=False,
        session_rth=True,
        session_after=False,
    )

    result = decide(inputs)

    assert result.side == "HOLD"
    assert result.conviction == 0.0
    assert result.reasons.get("spread_block") is True


def test_decision_extended_hours_buffer(monkeypatch):
    """Pre-market small edges fall into the no-trade buffer."""

    monkeypatch.setattr(decision_engine, "predict_p_up_latest", lambda interval: 0.515)
    monkeypatch.setattr(decision_engine, "vwap_distance_bps", lambda symbol: 0.0)
    _patch_quotes(monkeypatch, bid=10.0, ask=10.01)

    inputs = DecisionInputs(
        interval="5m",
        last_sentiment_daily=None,
        session_pre=True,
        session_rth=False,
        session_after=False,
    )

    result = decide(inputs)

    assert result.side == "HOLD"
    assert result.reasons.get("no_trade_buffer") is True


def test_decision_vwap_disagreement_downweights(monkeypatch):
    """VWAP disagreement nudges the gate and reduces conviction."""

    monkeypatch.setattr(state, "gate_threshold", 0.55, raising=False)
    monkeypatch.setattr(state, "w_model", 1.0, raising=False)
    monkeypatch.setattr(state, "w_sent", 0.0, raising=False)
    monkeypatch.setattr(decision_engine, "predict_p_up_latest", lambda interval: 0.62)
    monkeypatch.setattr(decision_engine, "vwap_distance_bps", lambda symbol: -50.0)
    _patch_quotes(monkeypatch, bid=10.0, ask=10.02)

    inputs = DecisionInputs(
        interval="5m",
        last_sentiment_daily=None,
        session_pre=False,
        session_rth=True,
        session_after=False,
    )

    result = decide(inputs)

    assert result.side == settings.TSLL_SYMBOL
    assert result.conviction < 1.0
    assert math.isclose(result.reasons.get("conviction_dw_vwap", 0.0), settings.CONVICTION_DW_VWAP)
