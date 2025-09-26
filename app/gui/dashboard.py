from __future__ import annotations
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt, QTimer, QTime, QDateTime
from app.gui.sparkline import Sparkline
from app.core.runtime_state import state, normalize_weights
from app.config.paths import DATA_DIR
from app.services.model import predict_p_up_latest, load_model
from app.services.market_data import get_quote
from app.services.pricing import spread_bps
from app.services.live_vwap import vwap_distance_bps
from app.services.alpaca_client import AlpacaService
from dotenv import dotenv_values
from app.core.app_config import AppConfig
import os, glob, json, math, pytz, datetime

NY = pytz.timezone("America/New_York")

def _read_daily_sentiment_score() -> float | None:
    sdir = DATA_DIR / "sentiment"
    files = sorted(glob.glob(os.path.join(sdir, "*.json")))
    if not files: return None
    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as f:
            doc = json.load(f)
        return float(doc.get("daily_score"))
    except Exception:
        return None

class Dashboard(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

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
        self._pup_vals = []
        self._sp_tsll_vals = []
        self._sp_tsdd_vals = []

        # Timers
        self.timer_fast = QTimer(self); self.timer_fast.timeout.connect(self._tick_fast); self.timer_fast.start(4000)
        self.timer_slow = QTimer(self); self.timer_slow.timeout.connect(self._tick_slow); self.timer_slow.start(30000)
        self._tick_fast(); self._tick_slow()

    def _tick_fast(self):
        # TSLA last
        q_tsla = get_quote("TSLA")
        try:
            self.lbl_tsla_last.setText(f"TSLA last: {q_tsla['last']:.2f}")
        except Exception:
            self.lbl_tsla_last.setText("TSLA last: (n/a)")

        # Quotes -> spreads
        q1 = get_quote("TSLL"); q2 = get_quote("TSDD")
        s1 = spread_bps(q1["bid"], q1["ask"]); s2 = spread_bps(q2["bid"], q2["ask"])
        if s1 == s1:  # not NaN
            self._sp_tsll_vals.append(s1); self._sp_tsll_vals = self._sp_tsll_vals[-60:]; self.sp_tsll.set_values(self._sp_tsll_vals)
        if s2 == s2:
            self._sp_tsdd_vals.append(s2); self._sp_tsdd_vals = self._sp_tsdd_vals[-60:]; self.sp_tsdd.set_values(self._sp_tsdd_vals)

        # Sentiment timestamp
        sdir = DATA_DIR / "sentiment"
        files = sorted(glob.glob(os.path.join(sdir, "*.json")))
        if files:
            ts = datetime.datetime.fromtimestamp(os.path.getmtime(files[-1]), tz=NY).strftime("%Y-%m-%d %H:%M %Z")
            self.lbl_sent.setText(f"Last sentiment file: {os.path.basename(files[-1])} (modified {ts})")

        # Sessions banner text
        self.lbl_session.setText(f"Sessions: Pre {'ON' if state.session_pre else 'OFF'} | RTH {'ON' if state.session_rth else 'OFF'} | After {'ON' if state.session_after else 'OFF'}")
        # Extended Hours OK banner only when Pre/After enabled and current time is within
        now = datetime.datetime.now(NY).time()
        pre_ok = state.session_pre and (now >= datetime.time(4,0) and now < datetime.time(9,30))
        aft_ok = state.session_after and (now >= datetime.time(16,0) and now < datetime.time(20,0))
        if pre_ok or aft_ok:
            self.lbl_ext.show()
        else:
            self.lbl_ext.hide()

        # PDT/Cash pill (best-effort)
        self._refresh_pdt_cash()

    def _tick_slow(self):
        # VWAP distance (RTH)
        try:
            d = vwap_distance_bps("TSLA")
            if d is None:
                self.lbl_vwap.setText("VWAP dist: (N/A)")
            else:
                self.lbl_vwap.setText(f"VWAP dist: {d:+.0f} bps")
        except Exception:
            self.lbl_vwap.setText("VWAP dist: (error)")

        # p_up and gate
        p_up = predict_p_up_latest(state.interval)
        if p_up == p_up:
            self._pup_vals.append(p_up); self._pup_vals = self._pup_vals[-60:]; self.sp_pup.set_values(self._pup_vals)
        daily = _read_daily_sentiment_score()
        if daily is not None and daily == daily:
            p_sent = (daily + 1.0)/2.0
            p_blend = state.w_model * (p_up if p_up==p_up else 0.5) + state.w_sent * p_sent
        else:
            p_blend = p_up
        th = state.gate_threshold
        if p_blend == p_blend:
            if p_blend >= th:
                self.gate_tile.setStyleSheet("background:#e6ffed; border:1px solid #7fd18b; color:#05400A; padding:10px;")
                self.lbl_gate.setText(f"Trade Gate: UP (TSLL) — signal={p_blend:.2f} ≥ {th:.2f}")
            else:
                self.gate_tile.setStyleSheet("background:#ffecec; border:1px solid #e0a0a0; color:#680000; padding:10px;")
                self.lbl_gate.setText(f"Trade Gate: DOWN (TSDD) — signal={p_blend:.2f} < {th:.2f}")
        else:
            self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")
            self.lbl_gate.setText("Trade Gate: (no signal)")

    def _refresh_pdt_cash(self):
        # Read keys and query Alpaca account quickly
        vals = dotenv_values(os.path.join(self._config.usb_keys_path, "keys.env")) or {}
        kid = vals.get("ALPACA_API_KEY_ID"); ksec = vals.get("ALPACA_API_SECRET_KEY")
        if not (kid and ksec):
            self.lbl_pdt.setText("PDT/Cash: (no Alpaca keys)")
            return
        try:
            alp = AlpacaService(kid, ksec)
            acct = alp.get_account()
            eq = float(getattr(acct, "equity", "0") or 0.0)
            nmbp = float(getattr(acct, "non_marginable_buying_power", "0") or 0.0)
            classification = (getattr(acct, "classification", "") or "").lower()
            day_count = int(getattr(acct, "daytrade_count", 0) or 0)
            if classification == "margin" and eq < 25000 and day_count >= 3:
                self.lbl_pdt.setText(f"PDT/Cash: BLOCK (margin < $25k & 3 daytrades) | Settled≈{nmbp:,.0f}")
                self.lbl_pdt.setStyleSheet("background:#ffecec; border:1px solid #e0a0a0; color:#680000; padding:4px;")
            else:
                self.lbl_pdt.setText(f"PDT/Cash: OK | Equity≈{eq:,.0f} | Settled≈{nmbp:,.0f}")
                self.lbl_pdt.setStyleSheet("")
        except Exception:
            self.lbl_pdt.setText("PDT/Cash: (error reading account)")
