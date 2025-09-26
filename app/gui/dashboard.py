from __future__ import annotations


"""Decision-focused dashboard with defensive background refreshers."""

import csv
import datetime as dt
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pytz
from dotenv import dotenv_values
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import settings as cfg
=======
import datetime
import glob
import json
import os
from typing import List

import pytz
from dotenv import dotenv_values
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

main
from app.config.paths import DATA_DIR
from app.core.app_config import AppConfig
from app.core.runtime_state import state
from app.gui.sparkline import Sparkline
from app.services.alpaca_client import AlpacaService
from app.services.decision_engine import DecisionInputs, DecisionResult, decide
=======
from app.services.live_vwap import vwap_distance_bps
from app.services.market_data import get_quote
from app.services.model import predict_p_up_latest
from app.services.pricing import spread_bps
main

NY = pytz.timezone(cfg.TZ)

=======
def _read_daily_sentiment_score() -> float | None:
    sdir = DATA_DIR / "sentiment"
    files = sorted(glob.glob(os.path.join(sdir, "*.json")))
    if not files:
        return None
    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as f:
            doc = json.load(f)
        return float(doc.get("daily_score"))
    except Exception:
        return None
main

@dataclass
class DashboardMetrics:
    """Container describing account metrics for display tiles."""

    equity: Optional[float] = None
    settled_cash: Optional[float] = None
    pnl_today: Optional[float] = None
    position_symbol: Optional[str] = None
    position_qty: Optional[float] = None
    position_price: Optional[float] = None
    last_trade_line: Optional[str] = None
    last_trade_filter: Optional[str] = None
    last_trade_ts: Optional[str] = None
    error: Optional[str] = None


class DecisionWorker(QObject):
    """Worker that computes a :class:`DecisionResult` off the UI thread."""

    finished = Signal(DecisionResult)
    failed = Signal(str)

    def __init__(self, interval: str, sentiment_dir: Path, session_flags: Tuple[bool, bool, bool]) -> None:
        super().__init__()
        self.interval = interval
        self.sentiment_dir = sentiment_dir
        self.session_flags = session_flags


    @Slot()
    def run(self) -> None:
=======
        v = QVBoxLayout(self)

        # Trade Gate tile
        self.gate_tile = QFrame()
        self.gate_tile.setFrameShape(QFrame.Box)
        self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")
        g = QVBoxLayout(self.gate_tile)
        self.lbl_gate = QLabel("Trade Gate: (no signal yet)")
        g.addWidget(self.lbl_gate)
        v.addWidget(self.gate_tile)
        tiles = QHBoxLayout()
        self.lbl_tsla_last = QLabel("TSLA last: (loading)")
        self.lbl_vwap = QLabel("VWAP dist: (N/A)")
        tiles.addWidget(self.lbl_tsla_last); tiles.addStretch(1); tiles.addWidget(self.lbl_vwap)
        v.addLayout(tiles)

        # Row: p_up sparkline + spread sparklines
        row = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(QLabel("p_up (last 60)"))
        self.sp_pup = Sparkline(); col1.addWidget(self.sp_pup)
        row.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("TSLL spread (bps, last 60)"))
        self.sp_tsll = Sparkline(); col2.addWidget(self.sp_tsll)
        row.addLayout(col2)

        col3 = QVBoxLayout()
        col3.addWidget(QLabel("TSDD spread (bps, last 60)"))
        self.sp_tsdd = Sparkline(); col3.addWidget(self.sp_tsdd)
        row.addLayout(col3)

        v.addLayout(row)

        # Row: session banners + PDT/Cash info
        info = QHBoxLayout()
        self.lbl_session = QLabel("Sessions: Pre ON | RTH ON | After OFF")
        self.lbl_ext = QLabel("Extended Hours OK")
        self.lbl_ext.setStyleSheet("background:#e6ffed; border:1px solid #7fd18b; color:#05400A; padding:4px;")
        self.lbl_pdt = QLabel("PDT/Cash: (fetching)")
        info.addWidget(self.lbl_session); info.addStretch(1); info.addWidget(self.lbl_ext); info.addStretch(1); info.addWidget(self.lbl_pdt)
        v.addLayout(info)

        # Last sentiment run
        self.lbl_sent = QLabel("Last sentiment run: (check Section 02 scheduler)")
        v.addWidget(self.lbl_sent)

        # Timer storage
        self._pup_vals: List[float] = []
        self._sp_tsll_vals: List[float] = []
        self._sp_tsdd_vals: List[float] = []

        # Timers
        self.timer_fast = QTimer(self); self.timer_fast.timeout.connect(self._tick_fast); self.timer_fast.start(4000)
        self.timer_slow = QTimer(self); self.timer_slow.timeout.connect(self._tick_slow); self.timer_slow.start(30000)
        self._tick_fast(); self._tick_slow()

    def _tick_fast(self):
        # TSLA last
        q_tsla = get_quote("TSLA")
main
        try:
            sentiment = _read_latest_sentiment(self.sentiment_dir)
            decision_inputs = DecisionInputs(
                interval=self.interval,
                last_sentiment_daily=sentiment,
                session_pre=self.session_flags[0],
                session_rth=self.session_flags[1],
                session_after=self.session_flags[2],
            )
            result = decide(decision_inputs)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - defensive surface only
            self.failed.emit(str(exc))


class MetricsWorker(QObject):
    """Worker that gathers account metrics and latest trade summary."""

    finished = Signal(DashboardMetrics)

    def __init__(self, config: AppConfig, sentiment_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.sentiment_dir = sentiment_dir

    @Slot()
    def run(self) -> None:
        metrics = DashboardMetrics()
        try:
            vals = dotenv_values(os.path.join(self.config.usb_keys_path, "keys.env")) or {}
            kid = vals.get("ALPACA_API_KEY_ID")
            ksec = vals.get("ALPACA_API_SECRET_KEY")
            if kid and ksec:
                alp = AlpacaService(kid, ksec)
                acct = alp.get_account()
                metrics.equity = _safe_float(getattr(acct, "equity", None))
                metrics.settled_cash = _safe_float(
                    getattr(acct, "non_marginable_buying_power", getattr(acct, "cash", None))
                )
                metrics.pnl_today = _safe_float(getattr(acct, "today_profit_loss", None))
                try:
                    pos_tsll = alp.get_position(cfg.TSLL_SYMBOL)
                except Exception:
                    pos_tsll = None
                try:
                    pos_tsdd = alp.get_position(cfg.TSDD_SYMBOL)
                except Exception:
                    pos_tsdd = None
                if pos_tsll:
                    metrics.position_symbol = cfg.TSLL_SYMBOL
                    metrics.position_qty = _safe_float(getattr(pos_tsll, "qty", None))
                    metrics.position_price = _safe_float(getattr(pos_tsll, "avg_entry_price", None))
                elif pos_tsdd:
                    metrics.position_symbol = cfg.TSDD_SYMBOL
                    metrics.position_qty = _safe_float(getattr(pos_tsdd, "qty", None))
                    metrics.position_price = _safe_float(getattr(pos_tsdd, "avg_entry_price", None))
            else:
                metrics.error = "Alpaca keys not detected on USB." if not kid else None
        except Exception as exc:  # pragma: no cover - defensive
            metrics.error = str(exc)

        last_line, last_filter, last_ts = _read_last_trade()
        metrics.last_trade_line = last_line
        metrics.last_trade_filter = last_filter
        metrics.last_trade_ts = last_ts
        self.finished.emit(metrics)


class BadgeLabel(QLabel):
    """Rounded badge used for session indicators."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setMargin(4)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.update_state(False)

    def update_state(self, active: bool, *, warning: bool = False) -> None:
        color = "#e6ffed" if active and not warning else "#ffecec" if warning else "#f0f0f0"
        border = "#7fd18b" if active and not warning else "#e0a0a0" if warning else "#d0d0d0"
        text = "#05400A" if active and not warning else "#680000" if warning else "#444444"
        self.setStyleSheet(
            f"background:{color}; color:{text}; border:1px solid {border}; border-radius:10px; padding:4px 8px;"
        )


class CardFrame(QFrame):
    """Reusable soft card frame with consistent padding and border."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame {"
            "background-color: rgba(255,255,255,0.9);"
            "border: 1px solid #d8d8d8;"
            "border-radius: 8px;"
            "}"
        )


class StatTile(CardFrame):
    """Small card presenting a single metric with headline typography."""

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight:600; font-size:13pt;")
        self.value = QLabel("—")
        self.value.setStyleSheet("font-size:20pt; font-weight:600;")
        self.value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addStretch(1)

    def update_value(self, text: str) -> None:
        self.value.setText(text)


class DecisionCard(CardFrame):
    """Card that visualises the decision engine output."""

    recompute_requested = Signal()
    dry_run_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Decision Engine")
        title.setStyleSheet("font-weight:600; font-size:14pt;")
        layout.addWidget(title)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.side_label = QLabel("HOLD")
        self.side_label.setAlignment(Qt.AlignCenter)
        self.side_label.setFixedWidth(90)
        self.side_label.setStyleSheet(
            "border-radius: 16px; padding:8px; font-weight:600; font-size:13pt;"
            "background:#f0f0f0; color:#444444;"
        )
        header.addWidget(self.side_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        self.lbl_p_up = QLabel("p_up: —")
        self.lbl_p_sent = QLabel("p_sent: —")
        self.lbl_p_blend = QLabel("p_blend: —")
        self.lbl_gate = QLabel("gate: —")
        self.lbl_conviction = QLabel("conviction: —")
        for idx, widget in enumerate(
            [self.lbl_p_up, self.lbl_p_sent, self.lbl_p_blend, self.lbl_gate, self.lbl_conviction]
        ):
            widget.setStyleSheet("font-size:12pt;")
            row = idx // 2
            col = idx % 2
            grid.addWidget(widget, row, col)
        header.addLayout(grid)
        header.addStretch(1)
        layout.addLayout(header)

        self.sparkline = Sparkline()
        self.sparkline.setMinimumHeight(40)
        layout.addWidget(self.sparkline)

        self.reason_row = QHBoxLayout()
        self.reason_row.setSpacing(8)
        layout.addLayout(self.reason_row)

        button_row = QHBoxLayout()
        self.btn_recompute = QPushButton("Recompute Now")
        self.btn_dry_run = QPushButton("Dry Run")
        for btn in (self.btn_recompute, self.btn_dry_run):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
        button_row.addWidget(self.btn_recompute)
        button_row.addWidget(self.btn_dry_run)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.btn_recompute.clicked.connect(self.recompute_requested.emit)
        self.btn_dry_run.clicked.connect(self.dry_run_requested.emit)

    def update_result(self, result: DecisionResult, history: List[float]) -> None:
        self.lbl_p_up.setText(f"p_up: {result.p_up:.3f}")
        self.lbl_p_sent.setText(f"p_sent: {result.p_sent:.3f}")
        self.lbl_p_blend.setText(f"p_blend: {result.p_blend:.3f}")
        self.lbl_gate.setText(f"gate: {result.gate:.3f}")
        self.lbl_conviction.setText(f"conviction: {result.conviction:.3f}")

        palette = {
            cfg.TSLL_SYMBOL: ("#0c3", "#ffffff"),
            cfg.TSDD_SYMBOL: ("#c30", "#ffffff"),
            "HOLD": ("#888888", "#f5f5f5"),
        }
        bg, fg = palette.get(result.side, ("#888888", "#f5f5f5"))
        self.side_label.setText(result.side)
        self.side_label.setStyleSheet(
            "border-radius: 16px; padding:8px; font-weight:600; font-size:13pt;"
            f"background:{bg}; color:{fg};"
        )

        reasons = {
            "spread_block": bool(result.reasons.get("spread_block", False)),
            "no_trade_buffer": bool(result.reasons.get("no_trade_buffer", False)),
            "vwap_disagree": bool(result.reasons.get("conviction_dw_vwap"))
            or bool(result.reasons.get("gate_adj_vwap")),
        }
        for i in reversed(range(self.reason_row.count())):
            item = self.reason_row.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for key, active in reasons.items():
            label = QLabel(f"{key}: {'Yes' if active else 'No'}")
            color = "#ffecec" if active else "#f2f2f2"
            text = "#680000" if active else "#444444"
            label.setStyleSheet(
                f"background:{color}; color:{text}; border-radius:10px; padding:4px 8px; font-size:10pt;"
            )
            self.reason_row.addWidget(label)
        self.reason_row.addStretch(1)

        self.sparkline.set_values(history)


class Dashboard(QWidget):
    """Dashboard combining decision output with key account telemetry."""

    decision_updated = Signal(DecisionResult, DashboardMetrics)
    show_logs_requested = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._decision_thread: Optional[QThread] = None
        self._metrics_thread: Optional[QThread] = None
        self._decision_history: List[float] = []
        self._latest_metrics = DashboardMetrics()

        self._build_ui()
        self._init_timers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.session_row = QHBoxLayout()
        self.session_row.setSpacing(8)
        self.badge_pre = BadgeLabel("PRE")
        self.badge_rth = BadgeLabel("RTH")
        self.badge_after = BadgeLabel("AFTER")
        self.badge_off = BadgeLabel("OFF")
        for badge in (self.badge_pre, self.badge_rth, self.badge_after, self.badge_off):
            self.session_row.addWidget(badge)
        self.session_row.addStretch(1)
        layout.addLayout(self.session_row)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(12)
        self.tile_equity = StatTile("Equity")
        self.tile_cash = StatTile("Settled Cash")
        self.tile_position = StatTile("Current Position")
        self.tile_pnl = StatTile("P&L Today")
        for tile in (self.tile_equity, self.tile_cash, self.tile_position, self.tile_pnl):
            tiles_row.addWidget(tile)
        layout.addLayout(tiles_row)

        self.decision_card = DecisionCard()
        layout.addWidget(self.decision_card)

        self.last_trade_button = QPushButton("Last trade: —")
        self.last_trade_button.setFlat(True)
        self.last_trade_button.setCursor(Qt.PointingHandCursor)
        self.last_trade_button.clicked.connect(self._open_last_trade)
        layout.addWidget(self.last_trade_button)

        layout.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888888; font-size:10pt;")
        layout.addWidget(self.status_label)

        self.decision_card.recompute_requested.connect(self.request_refresh)
        self.decision_card.dry_run_requested.connect(self.request_refresh)

    def _init_timers(self) -> None:
        self.decision_timer = QTimer(self)
        self.decision_timer.setInterval(2000)
        self.decision_timer.timeout.connect(self.request_refresh)
        self.decision_timer.start()

        self.metrics_timer = QTimer(self)
        self.metrics_timer.setInterval(5000)
        self.metrics_timer.timeout.connect(self._refresh_metrics)
        self.metrics_timer.start()

    @Slot()
    def request_refresh(self) -> None:
        if self._decision_thread and self._decision_thread.isRunning():
            return

        thread = QThread(self)
        worker = DecisionWorker(
            interval=state.interval,
            sentiment_dir=DATA_DIR / "sentiment",
            session_flags=(state.session_pre, state.session_rth, state.session_after),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_decision_result)
        worker.failed.connect(self._on_decision_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._decision_thread = thread
        thread.start()

    @Slot()
    def _refresh_metrics(self) -> None:
        if self._metrics_thread and self._metrics_thread.isRunning():
            return

        thread = QThread(self)
        worker = MetricsWorker(self._config, DATA_DIR / "sentiment")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_metrics)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._metrics_thread = thread
        thread.start()

    @Slot(DecisionResult)
    def _on_decision_result(self, result: DecisionResult) -> None:
        self._decision_history.append(result.p_blend)
        self._decision_history = self._decision_history[-120:]
        self.decision_card.update_result(result, self._decision_history)
        self._update_session_badges()
        self.status_label.setText(
            f"Max spread TSLL/TSDD: {result.spread_bps_tsll:.1f} / {result.spread_bps_tsdd:.1f} bps"
        )
        self.decision_updated.emit(result, self._latest_metrics)

    @Slot(str)
    def _on_decision_error(self, message: str) -> None:
        self.status_label.setText(f"Decision error: {message}")

    @Slot(DashboardMetrics)
    def _on_metrics(self, metrics: DashboardMetrics) -> None:
        self._latest_metrics = metrics
        self.tile_equity.update_value(_format_currency(metrics.equity))
        self.tile_cash.update_value(_format_currency(metrics.settled_cash))
        self.tile_pnl.update_value(_format_currency(metrics.pnl_today))

        if metrics.position_symbol and metrics.position_qty:
            qty = int(metrics.position_qty)
            price = metrics.position_price or 0.0
            self.tile_position.update_value(f"{metrics.position_symbol} @ {qty} ({price:.2f})")
        else:
            self.tile_position.update_value("None")

        if metrics.last_trade_line:
            self.last_trade_button.setText(f"Last trade: {metrics.last_trade_line}")
        else:
            self.last_trade_button.setText("Last trade: —")

        if metrics.error:
            self.status_label.setText(metrics.error)

    def _update_session_badges(self) -> None:
        now = dt.datetime.now(tz=NY)
        is_session = {
            "pre": state.session_pre and (dt.time(4, 0) <= now.time() < dt.time(9, 30)),
            "rth": state.session_rth and (dt.time(9, 30) <= now.time() < dt.time(16, 0)),
            "after": state.session_after and (dt.time(16, 0) <= now.time() < dt.time(20, 0)),
        }
        any_active = any(is_session.values())
        self.badge_pre.update_state(is_session["pre"])
        self.badge_rth.update_state(is_session["rth"])
        self.badge_after.update_state(is_session["after"])
        self.badge_off.update_state(not any_active, warning=not any_active)

    @Slot()
    def _open_last_trade(self) -> None:
        if self._latest_metrics.last_trade_filter:
            self.show_logs_requested.emit(self._latest_metrics.last_trade_filter)


def _read_latest_sentiment(sentiment_dir: Path) -> Optional[float]:
    if not sentiment_dir.exists():
        return None
    try:
        files = sorted(sentiment_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return None
    if not files:
        return None
    latest = files[0]
    try:
        with latest.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        score = float(payload.get("daily_score"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if math.isnan(score):
        return None
    return max(-1.0, min(1.0, score))


def _read_last_trade() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    trades_path = DATA_DIR / "trades.csv"
    if not trades_path.exists():
        return None, None, None
    try:
        with trades_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except (OSError, csv.Error):
        return None, None, None
    if not rows:
        return None, None, None
    last = rows[-1]
    ts = last.get("ts", "?")
    action = last.get("action", "?")
    symbol = last.get("symbol", "?")
    qty = last.get("qty", "?")
    price = last.get("price", last.get("px", "?"))
    summary = f"{ts} — {action} {symbol} x{qty} @ {price}"
    filter_token = last.get("decision_components_json") or symbol
    return summary, filter_token, ts


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        result = float(value)
        if math.isnan(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"
