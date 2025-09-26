from __future__ import annotations

import os
from typing import Optional
=======
main

from dotenv import dotenv_values
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.app_config import AppConfig
from app.core.runtime_state import state
from app.services.alpaca_client import AlpacaService
from app.services.market_data import get_quote
from app.services.model import predict_p_up_latest
from app.services.pricing import compute_entry_limit


class TradeControl(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._alp: Optional[AlpacaService] = None
        self._engine = None  # wired in Section 04 console; GUI control here is minimal
        v = QVBoxLayout(self)

        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        row = QHBoxLayout()
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        row.addStretch(1)
        v.addLayout(row)

        self.lbl_acct = QLabel("Account: (not connected)")
        self.lbl_hold = QLabel("Holding: (none)")
        self.lbl_preview = QLabel("Chosen limit preview: (n/a)")
        v.addWidget(self.lbl_acct)
        v.addWidget(self.lbl_hold)
        v.addWidget(self.lbl_preview)

        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(5000)
        self._tick()

    def _connect(self):
        vals = dotenv_values(os.path.join(self._config.usb_keys_path, "keys.env")) or {}
        kid = vals.get("ALPACA_API_KEY_ID")
        ksec = vals.get("ALPACA_API_SECRET_KEY")
        if kid and ksec:
            self._alp = AlpacaService(kid, ksec)

    def _start(self):
        self._connect()
        if not self._alp:
            self.lbl_acct.setText("Account: (no Alpaca keys)")
            return
        state.engine_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _stop(self):
        state.engine_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _tick(self):
        if not self._alp:
            self._connect()
        if self._alp:
            try:
                acct = self._alp.get_account()
                eq = float(getattr(acct, "equity", "0") or 0.0)
                nmbp = float(getattr(acct, "non_marginable_buying_power", "0") or 0.0)
                classification = getattr(acct, "classification", "")
                self.lbl_acct.setText(
                    f"Account: {classification} | Equity≈{eq:,.0f} | Settled≈{nmbp:,.0f}"
                )
                # holdings snapshot (best-effort)
                try:
                    posL = self._alp.get_position("TSLL")
                    posD = self._alp.get_position("TSDD")
                except Exception:
                    posL = posD = None
                if posL:
                    qty = getattr(posL, "qty", 0)
                    avg = getattr(posL, "avg_entry_price", "?")
                    self.lbl_hold.setText(
                        f"Holding: TSLL qty={qty} avg={avg}"
                    )
                elif posD:
                    qty = getattr(posD, "qty", 0)
                    avg = getattr(posD, "avg_entry_price", "?")
                    self.lbl_hold.setText(
                        f"Holding: TSDD qty={qty} avg={avg}"
                    )
                else:
                    self.lbl_hold.setText("Holding: (none)")
            except Exception:
                self.lbl_acct.setText("Account: (error)")

        # Preview chosen side & limit using gate
        p_up = predict_p_up_latest(state.interval)
        # get sentiment-blended
        # (Dashboard computes p_blend using last sentiment file; for preview,
        # keep it simple: use p_up)
        want_tsll = (p_up == p_up) and (p_up >= state.gate_threshold)
        sym = "TSLL" if want_tsll else "TSDD"
        q = get_quote(sym)
        entry = compute_entry_limit(
            "BUY", q["bid"], q["ask"], q["last"], state.slippage_bps
        )
        self.lbl_preview.setText(f"Chosen: {sym} @ limit≈{entry:.2f}")
