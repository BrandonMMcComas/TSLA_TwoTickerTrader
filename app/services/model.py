from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

import pandas as pd
from joblib import dump, load
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from app.config.paths import MODELS_DIR
from app.services.features import FEATURE_COLS, add_all_features, make_dataset
from app.services.history import fetch_tsla_bars

MODEL_PATH = MODELS_DIR / "tsla_direction_model.joblib"
@dataclass
class TrainResult:
    metrics: Dict[str, float]
    model_path: str
    n_train: int
    n_test: int
    interval: str
    lookback_days: int
    features: list
def _time_split(X: pd.DataFrame, y: pd.Series, test_frac: float = 0.2):
    n = len(X)
    n_test = max(50, int(n * test_frac))
    idx_split = n - n_test
    return X.iloc[:idx_split], X.iloc[idx_split:], y.iloc[:idx_split], y.iloc[idx_split:]
def train_direction_model(interval: str, lookback_days: int) -> TrainResult:
    df = fetch_tsla_bars(interval=interval, lookback_days=lookback_days)
    df_feat = add_all_features(df)
    X, y = make_dataset(df_feat)
    if len(X) < 200:
        raise RuntimeError("Not enough data after feature engineering to train (need >=200 rows).")
    Xtr, Xte, ytr, yte = _time_split(X, y, test_frac=0.2)
    scaler = StandardScaler()
    Xtr_s = scaler.fit_transform(Xtr.values)
    Xte_s = scaler.transform(Xte.values)
    clf = LogisticRegression(max_iter=1000, n_jobs=None)
    clf.fit(Xtr_s, ytr.values)
    proba = clf.predict_proba(Xte_s)[:,1]
    pred = (proba >= 0.5).astype(int)
    acc = accuracy_score(yte, pred)
    try:
        auc = roc_auc_score(yte, proba)
    except Exception:
        auc = float("nan")
    try:
        prec = precision_score(yte, pred, zero_division=0)
    except Exception:
        prec = float("nan")
    payload = {
        "model": clf,
        "scaler": scaler,
        "features": FEATURE_COLS,
        "interval": interval,
        "lookback_days": lookback_days,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {"accuracy": float(acc), "roc_auc": float(auc), "precision_up": float(prec)},
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dump(payload, MODEL_PATH)
    return TrainResult(metrics=payload["metrics"], model_path=str(MODEL_PATH),
                       n_train=len(Xtr), n_test=len(Xte),
                       interval=interval, lookback_days=lookback_days, features=FEATURE_COLS)
def load_model():
    if not MODEL_PATH.exists():
        return None
    return load(MODEL_PATH)
def predict_p_up_latest(interval: str) -> float:
    payload = load_model()
    if payload is None:
        return float("nan")
    if payload.get("interval") != interval:
        return float("nan")
    from app.services.features import FEATURE_COLS, add_all_features
    from app.services.history import fetch_tsla_bars
    df = fetch_tsla_bars(interval=interval, lookback_days=payload.get("lookback_days", 5))
    df_feat = add_all_features(df)
    X = df_feat[FEATURE_COLS].dropna()
    if X.empty:
        return float("nan")
    scaler = payload["scaler"]; clf = payload["model"]
    x_last = scaler.transform(X.iloc[[-1]].values)
    p = float(clf.predict_proba(x_last)[:,1][0])
    return p
