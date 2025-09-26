from __future__ import annotations


"""Interactive trading controls with live quote snapshots."""

import time
from dataclasses import dataclass
from typing import Dict, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import settings as cfg
=======
import os

from dotenv import dotenv_values
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

main
from app.core.app_config import AppConfig
from app.core.runtime_state import state
from app.gui.dashboard import DashboardMetrics
from app.services.decision_engine import DecisionResult
from app.services.market_data import get_quote
from app.services.pricing import spread_bps


@dataclass
class QuoteSnapshot:
    """Represents a lightweight view of quote data for the trading panel."""

    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    spread_bps: Optional[float] = None


class QuoteWorker(QObject):
    """Worker that fetches quotes for TSLL and TSDD without blocking the UI."""

    finished = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

    @Slot()
    def run(self) -> None:
        payload: Dict[str, QuoteSnapshot] = {}
        for symbol in (cfg.TSLL_SYMBOL, cfg.TSDD_SYMBOL):
            try:
                quote = get_quote(symbol)
                payload[symbol] = QuoteSnapshot(
                    bid=float(quote.get("bid")) if quote.get("bid") is not None else None,
                    ask=float(quote.get("ask")) if quote.get("ask") is not None else None,
                    last=float(quote.get("last")) if quote.get("last") is not None else None,
                    spread_bps=spread_bps(quote.get("bid"), quote.get("ask")),
                )
            except Exception:
                payload[symbol] = QuoteSnapshot()
        self.finished.emit(payload)
=======
from app.services.model import predict_p_up_latest
from app.services.pricing import compute_entry_limit
main


class TradeControl(QWidget):
    """Provides manual control hooks for the automated trading engine."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._quote_thread: Optional[QThread] = None
        self._latest_metrics = DashboardMetrics()
        self._latest_decision: Optional[DecisionResult] = None
        self._last_toast_ts = 0.0

        self._build_ui()
        self._init_timers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame {background: rgba(255,255,255,0.9); border:1px solid #d8d8d8; border-radius:8px;}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(12)

        title = QLabel("Trade Controls")
        title.setStyleSheet("font-weight:600; font-size:14pt;")
        card_layout.addWidget(title)

        self.status_badge = QLabel("Engine paused")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setStyleSheet(
            "border-radius:12px; padding:4px 12px; background:#ffecec; color:#680000; font-weight:600;"
        )
        card_layout.addWidget(self.status_badge)

        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(16)

        self.lbl_tsll = QLabel("TSLL — bid: — | ask: — | spread: — bps")
        self.lbl_tsdd = QLabel("TSDD — bid: — | ask: — | spread: — bps")
        self.lbl_target = QLabel("Target side: HOLD")
        self.lbl_cash = QLabel("Cash to use: —")
        self.lbl_cooldown = QLabel("Flip cooldown: ready")

        for idx, widget in enumerate(
            [self.lbl_tsll, self.lbl_tsdd, self.lbl_target, self.lbl_cash, self.lbl_cooldown]
        ):
            widget.setStyleSheet("font-size:11pt;")
            grid.addWidget(widget, idx, 0)

        card_layout.addLayout(grid)

        button_row = QHBoxLayout()
        self.btn_open = QPushButton("Open Position")
        self.btn_close = QPushButton("Close Position")
        for btn in (self.btn_open, self.btn_close):
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
        button_row.addWidget(self.btn_open)
        button_row.addWidget(self.btn_close)
        button_row.addStretch(1)
        card_layout.addLayout(button_row)

        layout.addWidget(card)
        layout.addStretch(1)

        self.toast = QLabel("")
        self.toast.setStyleSheet(
            "background: rgba(0,0,0,0.7); color:white; padding:6px 12px; border-radius:8px;"
        )
        self.toast.setAlignment(Qt.AlignCenter)
        self.toast.hide()
        layout.addWidget(self.toast, alignment=Qt.AlignCenter)

        self.btn_open.clicked.connect(self._handle_open)
        self.btn_close.clicked.connect(self._handle_close)
        self._update_button_state()

    def _init_timers(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self._refresh_quotes)
        self.timer.start()

        self.toast_timer = QTimer(self)
        self.toast_timer.setInterval(1500)
        self.toast_timer.timeout.connect(self._maybe_hide_toast)

    def update_decision(self, result: Optional[DecisionResult], metrics: DashboardMetrics) -> None:
        """Update target side, cash allocation, and cooldown labels."""

        self._latest_decision = result
        self._latest_metrics = metrics

        if result is None:
            self.lbl_target.setText("Target side: HOLD")
            self.lbl_cash.setText("Cash to use: —")
        else:
            self.lbl_target.setText(f"Target side: {result.side} (conviction {result.conviction:.2f})")
            cash = _compute_cash_to_use(metrics.settled_cash, result.conviction)
            self.lbl_cash.setText(f"Cash to use: {cash}")

        cooldown_text = _format_cooldown(metrics.last_trade_ts)
        self.lbl_cooldown.setText(f"Flip cooldown: {cooldown_text}")
        self._update_status_badge()

    def _refresh_quotes(self) -> None:
        if self._quote_thread and self._quote_thread.isRunning():
            return

        thread = QThread(self)
        worker = QuoteWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_quotes)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._quote_thread = thread
        thread.start()

    @Slot(dict)
    def _on_quotes(self, payload: Dict[str, QuoteSnapshot]) -> None:
        self._update_quote_label(self.lbl_tsll, cfg.TSLL_SYMBOL, payload)
        self._update_quote_label(self.lbl_tsdd, cfg.TSDD_SYMBOL, payload)

    def _update_quote_label(self, label: QLabel, symbol: str, payload: Dict[str, QuoteSnapshot]) -> None:
        snap = payload.get(symbol, QuoteSnapshot())
        if snap.bid is None or snap.ask is None:
            label.setText(f"{symbol} — bid: — | ask: — | spread: — bps")
            return
        spread = f"{snap.spread_bps:.1f}" if snap.spread_bps is not None else "—"
        label.setText(
            f"{symbol} — bid: {snap.bid:.2f} | ask: {snap.ask:.2f} | spread: {spread} bps"
        )

    def _handle_open(self) -> None:
        state.engine_running = True
        self._show_toast("Engine enabled; awaiting fills.")
        self._update_button_state()
        self._update_status_badge()

    def _handle_close(self) -> None:
        state.engine_running = False
        self._show_toast("Engine paused; new orders halted.")
        self._update_button_state()
        self._update_status_badge()

    def _update_status_badge(self) -> None:
        if state.engine_running:
            self.status_badge.setText("Engine active")
            self.status_badge.setStyleSheet(
                "border-radius:12px; padding:4px 12px; background:#e6ffed; color:#05400A; font-weight:600;"
            )
        else:
            self.status_badge.setText("Engine paused")
            self.status_badge.setStyleSheet(
                "border-radius:12px; padding:4px 12px; background:#ffecec; color:#680000; font-weight:600;"
            )

    def _update_button_state(self) -> None:
        self.btn_open.setEnabled(not state.engine_running)
        self.btn_close.setEnabled(state.engine_running)

    def _show_toast(self, message: str) -> None:
        self.toast.setText(message)
        self.toast.show()
        self._last_toast_ts = time.time()
        self.toast_timer.start()

    def _maybe_hide_toast(self) -> None:
        if time.time() - self._last_toast_ts > 1.5:
            self.toast.hide()
            self.toast_timer.stop()


def _compute_cash_to_use(settled_cash: Optional[float], conviction: float) -> str:
    if settled_cash is None:
        return "—"
    conviction = max(0.0, min(1.0, conviction))
    cash = settled_cash * (0.50 + 0.50 * conviction)
    return f"${cash:,.0f}"


def _format_cooldown(last_trade_ts: Optional[str]) -> str:
    if not last_trade_ts:
        return "ready"
    try:
        ts = time.strptime(last_trade_ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
        last_epoch = time.mktime(ts)
    except (ValueError, IndexError):
        return "ready"
    remaining = int(state.flip_cooldown_sec - (time.time() - last_epoch))
    if remaining <= 0:
        return "ready"
    return f"{remaining}s"
