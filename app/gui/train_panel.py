from __future__ import annotations


"""Training panel with non-blocking model retraining hooks."""

import glob
import os
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
=======
import glob
import json
import math
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
main
    QVBoxLayout,
    QWidget,
)


=======
from app.config import settings as cfg
main
from app.config.paths import DATA_DIR
from app.services.model import predict_p_up_latest, train_direction_model


@dataclass
class TrainResult:
    """Represents metrics returned from a training run."""

    accuracy: Optional[float]
    roc_auc: Optional[float]
    precision_up: Optional[float]
    n_train: int
    n_test: int


class TrainWorker(QObject):
    """Runs the heavy training task on a worker thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, interval: str, lookback_days: int) -> None:
        super().__init__()
        self.interval = interval
        self.lookback_days = lookback_days

    @Slot()
    def run(self) -> None:
        try:
            result = train_direction_model(self.interval, self.lookback_days)
            metrics = TrainResult(
                accuracy=result.metrics.get("accuracy"),
                roc_auc=result.metrics.get("roc_auc"),
                precision_up=result.metrics.get("precision_up"),
                n_train=result.n_train,
                n_test=result.n_test,
            )
            self.finished.emit(metrics)
        except Exception as exc:  # noqa: BLE001 - propagate to UI
            self.failed.emit(str(exc))


class TrainPanel(QWidget):
    """Minimal training launcher with dataset status and progress reporting."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._current_interval = "5m"
        self._lookback_days = 5

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QLabel("Model Training")
        header.setStyleSheet("font-weight:600; font-size:14pt;")
        layout.addWidget(header)

        self.dataset_label = QLabel(self._dataset_status())
        layout.addWidget(self.dataset_label)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.btn_train = QPushButton("Run Training")
        self.btn_train.clicked.connect(self._start_training)
        controls.addWidget(self.btn_train)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.result_label = QLabel("Metrics: (not trained yet)")
        layout.addWidget(self.result_label)

        self.status_label = QLabel("Tap Run Training to retrain the classifier.")
        layout.addWidget(self.status_label)

        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self._refresh_probabilities)
        self.timer.start()
        self._refresh_probabilities()

    def _dataset_status(self) -> str:
        sentiment_dir = DATA_DIR / "sentiment"
        files = glob.glob(os.path.join(sentiment_dir, "*.json"))
        return f"Dataset: {len(files)} sentiment files detected." if files else "Dataset: (no sentiment files)."

    @Slot()
    def _start_training(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self.progress.show()
        self.status_label.setText("Training in progress…")
        self.btn_train.setEnabled(False)

        thread = QThread(self)
        worker = TrainWorker(self._current_interval, self._lookback_days)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    @Slot(object)
    def _on_finished(self, metrics: TrainResult) -> None:
        self.progress.hide()
        self.btn_train.setEnabled(True)
        self.status_label.setText("Training completed successfully.")
        self.result_label.setText(
            "Metrics — "
            f"accuracy={metrics.accuracy or float('nan'):.3f}, "
            f"roc_auc={metrics.roc_auc or float('nan'):.3f}, "
            f"precision_up={metrics.precision_up or float('nan'):.3f}, "
            f"n_train={metrics.n_train}, n_test={metrics.n_test}"
        )
        self._refresh_probabilities()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.progress.hide()
        self.btn_train.setEnabled(True)
        self.status_label.setText("Training failed. See logs for details.")
        QMessageBox.warning(self, "Training Error", message)

    def _refresh_probabilities(self) -> None:
        p_up = predict_p_up_latest(self._current_interval)
        if p_up == p_up:
            self.status_label.setText(f"Latest p_up({self._current_interval}) = {p_up:.3f}")
        else:
            self.status_label.setText("Model probability unavailable.")
=======
def _read_daily_sentiment_score() -> float | None:
    """Return the most recent daily sentiment score if it can be read."""

    sentiment_dir = DATA_DIR / "sentiment"
    files = sorted(glob.glob(os.path.join(sentiment_dir, "*.json")))
    if not files:
        return None

    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        return float(document.get("daily_score"))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return None


class TrainPanel(QWidget):
    """Panel responsible for training and displaying model metrics."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)

        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("<b>Interval</b>"))

        self.cb_interval = QComboBox()
        self.cb_interval.addItems(["1m", "5m"])
        control_row.addWidget(self.cb_interval)

        control_row.addWidget(QLabel("<b>Lookback (days)</b>"))

        self.sb_days = QSpinBox()
        self.sb_days.setRange(1, 60)
        self.sb_days.setValue(5)
        control_row.addWidget(self.sb_days)

        self.btn_train = QPushButton("Train")
        control_row.addWidget(self.btn_train)

        layout.addLayout(control_row)

        self.lbl_metrics = QLabel("Metrics: (train to populate)")
        layout.addWidget(self.lbl_metrics)

        gate_row = QHBoxLayout()
        self.lbl_p_up = QLabel("p_up: –")
        self.lbl_p_blend = QLabel("p_blend: –")
        gate_row.addWidget(self.lbl_p_up)
        gate_row.addWidget(self.lbl_p_blend)
        gate_row.addStretch(1)
        gate_row.addWidget(QLabel("Gate threshold"))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(40)
        self.slider.setMaximum(70)
        self.slider.setValue(int(cfg.GATE_THRESHOLD_DEFAULT * 100))
        gate_row.addWidget(self.slider)

        self.lbl_thresh = QLabel(f"{cfg.GATE_THRESHOLD_DEFAULT:.2f}")
        gate_row.addWidget(self.lbl_thresh)

        layout.addLayout(gate_row)

        self.gate_tile = QFrame()
        self.gate_tile.setFrameShape(QFrame.Box)
        self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")

        self.gate_text = QLabel("Trade Gate: (no model yet)")
        gate_tile_layout = QVBoxLayout(self.gate_tile)
        gate_tile_layout.addWidget(self.gate_text)
        layout.addWidget(self.gate_tile)

        layout.addStretch(1)

        self.btn_train.clicked.connect(self._do_train)
        self.slider.valueChanged.connect(self._on_thresh_change)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_probs)
        self.timer.start(30_000)

        self._refresh_probs()

    def _on_thresh_change(self, value: int) -> None:
        self.lbl_thresh.setText(f"{value / 100.0:.2f}")
        self._update_gate_tile()

    def _update_gate_tile(self) -> None:
        def parse(label: QLabel) -> float:
            try:
                return float(label.text().split(":")[1].strip())
            except (IndexError, ValueError):
                return float("nan")

        p_up = parse(self.lbl_p_up)
        p_blend = parse(self.lbl_p_blend)
        threshold = self.slider.value() / 100.0
        chosen = p_blend if not math.isnan(p_blend) else p_up

        if math.isnan(chosen):
            self.gate_text.setText("Trade Gate: (no signal)")
            self.gate_tile.setStyleSheet("background:#f7f7f7; padding:10px;")
            return

        if chosen >= threshold:
            self.gate_text.setText(
                f"Trade Gate: UP (TSLL) — signal={chosen:.2f} ≥ threshold {threshold:.2f}"
            )
            self.gate_tile.setStyleSheet(
                "background:#e6ffed; border:1px solid #7fd18b; color:#05400A; padding:10px;"
            )
        else:
            self.gate_text.setText(
                f"Trade Gate: DOWN (TSDD) — signal={chosen:.2f} < threshold {threshold:.2f}"
            )
            self.gate_tile.setStyleSheet(
                "background:#ffecec; border:1px solid #e0a0a0; color:#680000; padding:10px;"
            )

    def _do_train(self) -> None:
        self.btn_train.setEnabled(False)
        self.btn_train.setText("Training…")

        try:
            result = train_direction_model(
                self.cb_interval.currentText(),
                self.sb_days.value(),
            )
        except Exception as exc:  # noqa: BLE001 - surface to GUI
            self.lbl_metrics.setText(f"Training error: {exc}")
        else:
            metrics = result.metrics
            self.lbl_metrics.setText(
                "Metrics — Acc: "
                f"{metrics.get('accuracy', float('nan')):.3f} | "
                f"ROC AUC: {metrics.get('roc_auc', float('nan')):.3f} | "
                f"Precision(up): {metrics.get('precision_up', float('nan')):.3f} | "
                f"n_train={result.n_train}, n_test={result.n_test}"
            )
        finally:
            self.btn_train.setEnabled(True)
            self.btn_train.setText("Train")
            self._refresh_probs()

    def _refresh_probs(self) -> None:
        p_up = predict_p_up_latest(self.cb_interval.currentText())
        if p_up == p_up:  # check for NaN
            self.lbl_p_up.setText(f"p_up: {p_up:.3f}")
        else:
            self.lbl_p_up.setText("p_up: –")

        daily = _read_daily_sentiment_score()
        if daily is not None and daily == daily:
            probability_from_sentiment = (daily + 1.0) / 2.0
            model_weight = p_up if p_up == p_up else 0.5
            blended = (
                cfg.BLEND_W_MODEL * model_weight
                + cfg.BLEND_W_SENT * probability_from_sentiment
            )
            self.lbl_p_blend.setText(f"p_blend: {blended:.3f}")
        else:
            self.lbl_p_blend.setText("p_blend: –")

        self._update_gate_tile()
main
