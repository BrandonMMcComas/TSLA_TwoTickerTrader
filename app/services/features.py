from __future__ import annotations
import pandas as pd
import numpy as np
def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()
def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()
def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi
def _bb(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    percentB = (series - lower) / (upper - lower)
    bandwidth = (upper - lower) / mid
    return percentB, bandwidth
def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    vwap = pd.Series(0.0, index=df.index)
    for date, grp in df[df["IsRTH"]].groupby(df["Date"]):
        pv = (typical.loc[grp.index] * df["Volume"].loc[grp.index]).cumsum()
        vv = df["Volume"].loc[grp.index].cumsum().replace(0, np.nan)
        vwap.loc[grp.index] = (pv / vv).fillna(method="ffill").fillna(method="bfill")
    return vwap
def _overnight_gap(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(0.0, index=df.index)
    by_date = df.groupby(df["Date"])
    prev_close = None
    for date, grp in by_date:
        rth = grp[grp["IsRTH"]]
        if not rth.empty and prev_close is not None:
            open_930 = rth["Open"].iloc[0]
            gap = (open_930 - prev_close) / prev_close if prev_close not in (0, None) else 0.0
            out.loc[rth.index] = gap
        prev_close = grp.loc[grp["IsRTH"]].iloc[-1]["Close"] if not rth.empty else prev_close
    return out
def add_all_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]; vol = out["Volume"].astype(float)
    out["ret_1"] = close.pct_change(1)
    out["ret_5"] = close.pct_change(5)
    sma5 = _sma(close, 5); sma20 = _sma(close, 20)
    ema12 = _ema(close, 12); ema26 = _ema(close, 26)
    out["sma_5_slope"] = sma5.pct_change()
    out["sma_20_slope"] = sma20.pct_change()
    out["ema_12_slope"] = ema12.pct_change()
    out["ema_26_slope"] = ema26.pct_change()
    rsi14 = _rsi(close, 14)
    out["rsi_14"] = rsi14 / 100.0
    macd = ema12 - ema26
    macd_signal = _ema(macd, 9)
    out["macd"] = macd
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd - macd_signal
    vol_mean = vol.rolling(50, min_periods=50).mean()
    vol_std = vol.rolling(50, min_periods=50).std(ddof=0)
    out["vol_z"] = (vol - vol_mean) / (vol_std.replace(0, np.nan))
    minutes_of_day = out.index.hour * 60 + out.index.minute
    out["tod_sin"] = np.sin(2 * np.pi * minutes_of_day / 1440.0)
    out["tod_cos"] = np.cos(2 * np.pi * minutes_of_day / 1440.0)
    bb_p, bb_bw = _bb(close, 20, 2.0)
    out["bb_percentB"] = bb_p
    out["bb_bandwidth"] = bb_bw
    vwap = _session_vwap(out)
    vw_dist = (close - vwap) / vwap.replace(0, np.nan)
    vw_dist = vw_dist.where(out["IsRTH"], 0.0)
    out["vwap_dist_rth"] = vw_dist
    out["overnight_gap"] = _overnight_gap(out)
    return out
FEATURE_COLS = [
    "ret_1","ret_5",
    "sma_5_slope","sma_20_slope","ema_12_slope","ema_26_slope",
    "rsi_14","macd","macd_signal","macd_hist",
    "vol_z","tod_sin","tod_cos",
    "bb_percentB","bb_bandwidth",
    "vwap_dist_rth","overnight_gap"
]
def make_dataset(df_feat: pd.DataFrame):
    y = (df_feat["Close"].shift(-1) > df_feat["Close"]).astype(int)
    X = df_feat[FEATURE_COLS]
    mask = X.notna().all(axis=1) & y.notna()
    X = X[mask]; y = y[mask]
    return X, y
