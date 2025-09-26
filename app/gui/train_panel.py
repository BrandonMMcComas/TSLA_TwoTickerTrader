from __future__ import annotations
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QSlider, QFrame
from PySide6.QtCore import Qt, QTimer
from app.services.model import train_direction_model, predict_p_up_latest
from app.config import settings as cfg
from app.config.paths import DATA_DIR
import os, json, glob, math
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
class TrainPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("<b>Interval</b>"))
        self.cb_interval = QComboBox(); self.cb_interval.addItems(["1m","5m"])
        row.addWidget(self.cb_interval)
        row.addWidget(QLabel("<b>Lookback (days)</b>"))
        self.sb_days = QSpinBox(); self.sb_days.setRange(1, 60); self.sb_days.setValue(5)
        row.addWidget(self.sb_days)
        self.btn_train = QPushButton("Train"); row.addWidget(self.btn_train)
        v.addLayout(row)
        self.lbl_metrics = QLabel("Metrics: (train to populate)")
        v.addWidget(self.lbl_metrics)
        gate_row = QHBoxLayout()
        self.lbl_p_up = QLabel("p_up: –")
        self.lbl_p_blend = QLabel("p_blend: –")
        gate_row.addWidget(self.lbl_p_up); gate_row.addWidget(self.lbl_p_blend); gate_row.addStretch(1)
        gate_row.addWidget(QLabel("Gate threshold"))
        self.slider = QSlider(Qt.Horizontal); self.slider.setMinimum(40); self.slider.setMaximum(70); self.slider.setValue(int(cfg.GATE_THRESHOLD_DEFAULT*100))
        gate_row.addWidget(self.slider)
        self.lbl_thresh = QLabel(f"{cfg.GATE_THRESHOLD_DEFAULT:.2f}"); gate_row.addWidget(self.lbl_thresh)
        v.addLayout(gate_row)
        self.gate_tile = QFrame(); self.gate_tile.setFrameShape(QFrame.Box); self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")
        self.gate_text = QLabel("Trade Gate: (no model yet)")
        tlay = QVBoxLayout(self.gate_tile); tlay.addWidget(self.gate_text); v.addWidget(self.gate_tile)
        v.addStretch(1)
        self.btn_train.clicked.connect(self._do_train)
        self.slider.valueChanged.connect(self._on_thresh_change)
        self.timer = QTimer(self); self.timer.timeout.connect(self._refresh_probs); self.timer.start(30000)
        self._refresh_probs()
    def _on_thresh_change(self, val: int):
        self.lbl_thresh.setText(f"{val/100.0:.2f}"); self._update_gate_tile()
    def _update_gate_tile(self):
        def parse(lbl: QLabel):
            try:
                return float(lbl.text().split(":")[1].strip())
            except Exception: return float("nan")
        p_up = parse(self.lbl_p_up); p_blend = parse(self.lbl_p_blend)
        th = self.slider.value()/100.0
        which = p_blend if not math.isnan(p_blend) else p_up
        if not math.isnan(which):
            if which >= th:
                self.gate_text.setText(f"Trade Gate: UP (TSLL) — signal={which:.2f} ≥ threshold {th:.2f}")
                self.gate_tile.setStyleSheet("background:#e6ffed; border:1px solid #7fd18b; color:#05400A; padding:10px;")
            else:
                self.gate_text.setText(f"Trade Gate: DOWN (TSDD) — signal={which:.2f} < threshold {th:.2f}")
                self.gate_tile.setStyleSheet("background:#ffecec; border:1px solid #e0a0a0; color:#680000; padding:10px;")
        else:
            self.gate_text.setText("Trade Gate: (no signal)")
            self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")
    def _do_train(self):
        self.btn_train.setEnabled(False); self.btn_train.setText("Training…")
        try:
            res = train_direction_model(self.cb_interval.currentText(), self.sb_days.value())
            m = res.metrics
            self.lbl_metrics.setText(f"Metrics — Acc: {m.get('accuracy', float('nan')):.3f} | ROC AUC: {m.get('roc_auc', float('nan')):.3f} | Precision(up): {m.get('precision_up', float('nan')):.3f} | n_train={res.n_train}, n_test={res.n_test}")
        except Exception as e:
            self.lbl_metrics.setText(f"Training error: {e}")
        finally:
            self.btn_train.setEnabled(True); self.btn_train.setText("Train")
            self._refresh_probs()
    def _refresh_probs(self):
        p_up = predict_p_up_latest(self.cb_interval.currentText())
        if p_up == p_up: self.lbl_p_up.setText(f"p_up: {p_up:.3f}")
        else: self.lbl_p_up.setText("p_up: –")
        daily = _read_daily_sentiment_score()
        if daily is not None and daily == daily:
            p_sent = (daily + 1.0)/2.0
            p_blend = cfg.BLEND_W_MODEL * (p_up if p_up==p_up else 0.5) + cfg.BLEND_W_SENT * p_sent
            self.lbl_p_blend.setText(f"p_blend: {p_blend:.3f}")
        else:
            self.lbl_p_blend.setText("p_blend: –")
        self._update_gate_tile()
