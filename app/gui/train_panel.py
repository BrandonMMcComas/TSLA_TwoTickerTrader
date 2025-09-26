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
    QVBoxLayout,
    QWidget,
)

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
