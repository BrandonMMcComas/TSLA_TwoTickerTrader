from __future__ import annotations

import csv
import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, cast

import pytz
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce

from app.config import settings
from app.services import pricing
from app.services.alpaca_client import AlpacaService

# NOTE: We assume a MarketData service exists with get_quote(symbol) -> dict(bid, ask, last, ts).
Quote = Dict[str, Any]
_market_get_quote: Optional[Callable[[str], Quote]]

try:
    from app.services.market_data import get_quote as _imported_get_quote
except Exception:
    _market_get_quote = None
else:
    _market_get_quote = cast(Callable[[str], Quote], _imported_get_quote)


def get_quote(symbol: str) -> Quote:
    if _market_get_quote is not None:
        result = _market_get_quote(symbol)
        return cast(Quote, result)

    # Placeholder fake quote to keep imports sane if service isn't running.
    now = datetime.now(tz=pytz.timezone(settings.TZ))
    return {"symbol": symbol, "bid": 100.0, "ask": 100.5, "last": 100.2, "ts": now}

NY = pytz.timezone(settings.TZ)

@dataclass
class ReplaceState:
    last_ts: float = 0.0
    count: int = 0
    cooling_until: float = 0.0

class TraderEngine:
    """
    Limit-only trading engine with FOK-like behavior pre/post per v3 spec.
    One-position policy: TSLL (long) or TSDD (long).
    """
    def __init__(self, alpaca: AlpacaService, data_dir: Path = Path("data")):
        self.alpaca = alpaca
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.data_dir = data_dir
        self.trades_csv = data_dir / "trades.csv"
        self.risk = settings.RiskSettings()
        self.session = settings.SessionToggles()
        self._replace_state: Dict[str, ReplaceState] = {}  # order_id -> state
        self._peaks: Dict[str, float] = {}
        self._ensure_csv()

    # --------------- Public control ---------------
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, name="TraderEngine", daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # --------------- Core loop ---------------
    def _run_loop(self):
        while self.running:
            try:
                self.process_once()
            except Exception as e:
                # Fail closed — log and continue (GUI logs will pick up the exception traceback).
                print(f"[TraderEngine] Error: {e}")
            time.sleep(0.5)

    def process_once(self):
        # Check sessions and account status
        if not self._session_allowed():
            return

        acct = self.alpaca.get_account()
        # Fail closed if account blocked
        if getattr(acct, "trading_blocked", False) or getattr(acct, "account_blocked", False):
            return

        # Enforce cash-only using settled cash proxy (non_marginable_buying_power)
        settled_cash_str = getattr(acct, "non_marginable_buying_power", None) or getattr(acct, "cash", "0")
        try:
            settled_cash = float(settled_cash_str)
        except Exception:
            settled_cash = 0.0

        equity = float(getattr(acct, "equity", "0") or 0)

        # PDT block for margin accounts < $25k (best-effort using account fields)
        if self._is_margin_account(acct) and equity < 25_000:
            day_count = int(getattr(acct, "daytrade_count", 0) or 0)
            if day_count >= 3:
                # GUI should surface a banner; here we simply skip
                return

        # What are we holding?
        pos_tsll = self.alpaca.get_position(settings.TSLL_SYMBOL)
        pos_tsdd = self.alpaca.get_position(settings.TSDD_SYMBOL)
        holding = settings.TSLL_SYMBOL if pos_tsll else (settings.TSDD_SYMBOL if pos_tsdd else None)

        # Get quotes for both tickers to compute spreads and pricing previews
        q_tsll = get_quote(settings.TSLL_SYMBOL)
        q_tsdd = get_quote(settings.TSDD_SYMBOL)

        # Spread guards — if either side we might trade has a too-wide spread, wait
        spread_tsll = pricing.spread_bps(q_tsll["bid"], q_tsll["ask"])
        spread_tsdd = pricing.spread_bps(q_tsdd["bid"], q_tsdd["ask"])
        if max(spread_tsll, spread_tsdd) > self.risk.spread_max_bps:
            return

        # Decide desired side using external gate signal (Section 03 provides it).
        # Here, we expect someone to set the 'target_side' externally via GUI or a service.
        target_side = self._decide_target_side_fallback()

        # Enforce one-position policy and flip if needed
        if holding and holding != target_side:
            # Close current position then open opposite (flip)
            self._close_position_limit(holding)
            # Optional cooldown can be applied here (default 0)
            self._open_side(target_side, settled_cash)
        elif not holding:
            # Open new position
            self._open_side(target_side, settled_cash)
        else:
            # Manage exits (P80 TP & trailing stop-limit maintenance)
            self._manage_position(holding)

    # --------------- Helpers ---------------
    def _decide_target_side_fallback(self) -> str:
        """
        Placeholder: in Section 03 the p_blend gate sets desired side.
        Here we just use TSLL as a default to keep engine sane if not wired.
        """
        return settings.TSLL_SYMBOL

    def _session_allowed(self) -> bool:
        now = datetime.now(NY)
        tod = now.time()
        pre = self.session.pre and (tod >= datetime.strptime("04:00", "%H:%M").time()) and (tod < datetime.strptime("09:30", "%H:%M").time())
        rth = self.session.rth and (tod >= datetime.strptime("09:30", "%H:%M").time()) and (tod < datetime.strptime("16:00", "%H:%M").time())
        after = self.session.after and (tod >= datetime.strptime("16:00", "%H:%M").time()) and (tod < datetime.strptime("20:00", "%H:%M").time())
        return pre or rth or after

    def _is_margin_account(self, acct) -> bool:
        # Heuristic: daytrading_buying_power exists/ > 0 or pattern_day_trader field present.
        dtbp = float(getattr(acct, "daytrading_buying_power", "0") or 0)
        classification = getattr(acct, "classification", "")  # "margin" or "cash" on some envs
        return dtbp > 0 or classification.lower() == "margin"

    def _choose_symbols(self, desired: str):
        if desired == settings.TSLL_SYMBOL:
            return settings.TSLL_SYMBOL, OrderSide.BUY, settings.TSDD_SYMBOL
        else:
            return settings.TSDD_SYMBOL, OrderSide.BUY, settings.TSLL_SYMBOL

    def _open_side(self, desired_symbol: str, settled_cash: float):
        sym, side, other = self._choose_symbols(desired_symbol)
        q = get_quote(sym)
        entry_limit = pricing.compute_entry_limit(
            "BUY", q["bid"], q["ask"], q["last"], self.risk.slippage_bps
        )
        qty = math.floor(settled_cash / entry_limit)
        if qty < 1:
            return

        # Guard: extended hours require LIMIT + DAY + extended_hours=True
        extended = self._is_extended_now()
        tif = TimeInForce.DAY

        if extended:
            # Emulate FOK-like behavior per spec
            self._emulated_fok(sym, qty, side, entry_limit)
        else:
            # Submit standard limit and manage replaces while open
            order = self.alpaca.submit_limit(
                symbol=sym, qty=qty, side=side, limit_price=entry_limit, tif=tif, extended_hours=False
            )
            self._manage_open_limit(order.id, sym, "BUY")

        # Place protective stop-limit once we have/confirm a position
        pos = self.alpaca.get_position(sym)
        if pos:
            avg = float(getattr(pos, "avg_entry_price", "0"))
            stop_px, stop_lmt = pricing.compute_stop_limit(
                avg, settings.STOP_LOSS_PCT_DEFAULT, settings.STOP_LIMIT_OFFSET_BPS_DEFAULT
            )
            try:
                self.alpaca.submit_stop_limit(
                    symbol=sym, qty=float(getattr(pos, "qty", 0)), side=OrderSide.SELL,  # exit protection
                    stop_price=stop_px, limit_price=stop_lmt, tif=TimeInForce.DAY, extended_hours=False
                )
            except Exception as e:
                print(f"[TraderEngine] stop-limit submit failed (will continue RTH-only): {e}")

        self._log_trade("ENTRY", sym, qty, entry_limit, note="open_side")

    def _close_position_limit(self, symbol: str):
        pos = self.alpaca.get_position(symbol)
        if not pos:
            return
        qty = float(getattr(pos, "qty", 0))
        q = get_quote(symbol)
        limit_px = pricing.compute_entry_limit("SELL", q["bid"], q["ask"], q["last"], self.risk.slippage_bps)

        extended = self._is_extended_now()
        tif = TimeInForce.DAY
        side = OrderSide.SELL

        if extended:
            self._emulated_fok(symbol, qty, side, limit_px)
        else:
            order = self.alpaca.submit_limit(
                symbol=symbol, qty=qty, side=side, limit_price=limit_px, tif=tif, extended_hours=False
            )
            self._manage_open_limit(order.id, symbol, "SELL")

        self._log_trade("EXIT", symbol, qty, limit_px, note="flip_close")

    def _manage_position(self, symbol: str):
        # Track P80 take-profit using current vs peak
        pos = self.alpaca.get_position(symbol)
        if not pos:
            return
        avg = float(getattr(pos, "avg_entry_price", "0"))
        qty = float(getattr(pos, "qty", "0"))
        if qty <= 0:
            return
        q = get_quote(symbol)
        last = q["last"]
        # Keep a simple peak tracker in-memory (could be moved to persistent if needed)
        key = f"peak:{symbol}"
        peak = self._peaks.get(key, last)
        peak = max(peak, last)
        self._peaks[key] = peak
        p80 = avg + 0.8 * (peak - avg)
        if last <= p80 and peak > avg:
            # Take profit via limit
            limit_px = pricing.compute_entry_limit("SELL", q["bid"], q["ask"], q["last"], self.risk.slippage_bps)
            self.alpaca.submit_limit(
                symbol=symbol, qty=qty, side=OrderSide.SELL, limit_price=limit_px, tif=TimeInForce.DAY, extended_hours=False
            )
            # No flip here; flip policy is handled by outer signal change
            self._log_trade("TP80_EXIT", symbol, qty, limit_px, note=f"avg={avg},peak={peak},p80={p80}")

    def _manage_open_limit(self, order_id: str, symbol: str, side_txt: str):
        # Replace throttle while order is open during RTH
        state = self._replace_state.setdefault(order_id, ReplaceState())
        while True:
            o = self.alpaca.get_order(order_id)
            if o.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED,
                            OrderStatus.PARTIALLY_FILLED):
                break
            now = time.time()
            if now < state.cooling_until:
                time.sleep(0.25)
                continue
            q = get_quote(symbol)
            if side_txt == "BUY":
                new_px = pricing.compute_entry_limit("BUY", q["bid"], q["ask"], q["last"], self.risk.slippage_bps)
            else:
                new_px = pricing.compute_entry_limit("SELL", q["bid"], q["ask"], q["last"], self.risk.slippage_bps)
            try:
                # only replace if limit moved > 15 bps
                old_px = float(getattr(o, "limit_price", "0") or 0)
                if old_px > 0:
                    move_bps = abs((new_px - old_px) / old_px) * 10_000.0
                else:
                    move_bps = 0.0
                if (now - state.last_ts) >= self.risk.replace_min_interval_sec and move_bps > self.risk.replace_bps_threshold:
                    o = self.alpaca.replace_limit(order_id, new_limit_price=round(new_px, 4))
                    state.last_ts = now
                    state.count += 1
                    if state.count >= self.risk.replace_max_count:
                        # Cool-off 10–20s (use lower bound)
                        state.cooling_until = now + self.risk.replace_cooldown_sec[0]
                        state.count = 0
                time.sleep(0.25)
            except Exception:
                break

    def _emulated_fok(self, symbol: str, qty: float, side: OrderSide, limit_price: float):
        # Submit extended-hours LIMIT+DAY with quick windows; keep partials.
        remaining = qty
        windows = 0
        while remaining > 0 and windows < self.risk.fok_max_windows:
            windows += 1
            order = self.alpaca.submit_limit(
                symbol=symbol, qty=remaining, side=side, limit_price=limit_price, tif=TimeInForce.DAY, extended_hours=True
            )
            time.sleep(self.risk.fok_window_ms / 1000.0)
            o = self.alpaca.get_order(order.id)
            filled = float(getattr(o, "filled_qty", 0) or 0)
            if filled >= remaining:
                break
            # cancel remainder if any
            try:
                self.alpaca.cancel_order(order.id)
            except Exception:
                pass
            remaining = max(0, remaining - filled)
            if remaining <= 0:
                break
            # quick re-check against quotes for next window
            q = get_quote(symbol)
            limit_price = pricing.compute_entry_limit("BUY" if side == OrderSide.BUY else "SELL",
                                                     q["bid"], q["ask"], q["last"], self.risk.slippage_bps)

    def _is_extended_now(self) -> bool:
        now = datetime.now(NY).time()
        return (self.session.pre and datetime.strptime("04:00", "%H:%M").time() <= now < datetime.strptime("09:30", "%H:%M").time()) or \
               (self.session.after and datetime.strptime("16:00", "%H:%M").time() <= now < datetime.strptime("20:00", "%H:%M").time())

    def _ensure_csv(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.trades_csv.exists():
            with open(self.trades_csv, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts","action","symbol","qty","px","entry_limit","exit_limit","stop_limit","cash_before","cash_after",
                            "prob_up","sentiment","p80_threshold","session","slippage_bps_used","spread_bps","decision_components_json","note"])

    def _log_trade(self, action: str, symbol: str, qty: float, px: float, note: str = ""):
        ts = datetime.now(NY).isoformat()
        with open(self.trades_csv, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([ts, action, symbol, qty, px, "", "", "", "", "", "", "", "", self._session_str(),
                        self.risk.slippage_bps, "", json.dumps({}), note])

    def _session_str(self) -> str:
        now = datetime.now(NY).time()
        if datetime.strptime("04:00", "%H:%M").time() <= now < datetime.strptime("09:30", "%H:%M").time():
            return "PRE"
        if datetime.strptime("09:30", "%H:%M").time() <= now < datetime.strptime("16:00", "%H:%M").time():
            return "RTH"
        if datetime.strptime("16:00", "%H:%M").time() <= now < datetime.strptime("20:00", "%H:%M").time():
            return "AFTER"
        return "OFF"
