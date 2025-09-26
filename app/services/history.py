from __future__ import annotations

import pandas as pd
import pytz
import yfinance as yf

NY = pytz.timezone("America/New_York")


def _cap_period(interval: str, lookback_days: int) -> str:
    if interval == "1m":
        days = min(lookback_days, 7)
        return f"{days}d"
    elif interval == "5m":
        days = min(lookback_days, 60)
        return f"{days}d"
    else:
        raise ValueError("interval must be '1m' or '5m'")


def fetch_tsla_bars(interval: str = "1m", lookback_days: int = 5) -> pd.DataFrame:
    period = _cap_period(interval, lookback_days)
    tkr = yf.Ticker("TSLA")
    df = tkr.history(
        period=period,
        interval=interval,
        prepost=True,
        actions=False,
        raise_errors=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(NY)
    else:
        df.index = df.index.tz_convert(NY)
    df = df.rename(columns={c: c.capitalize() for c in df.columns})
    df["Date"] = df.index.date
    df["IsRTH"] = (
        (df.index.hour > 9) | ((df.index.hour == 9) & (df.index.minute >= 30))
    ) & (df.index.hour < 16)
    return df[["Open", "High", "Low", "Close", "Volume", "Date", "IsRTH"]].copy()
