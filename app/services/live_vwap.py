from __future__ import annotations
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time
import pytz

NY = pytz.timezone("America/New_York")

def rth_session_now():
    now = datetime.now(NY).time()
    return time(9,30) <= now < time(16,0)

def vwap_distance_bps(symbol: str = "TSLA") -> float | None:
    """
    Compute RTH-anchored VWAP distance in basis points for today's session.
    Returns None if not RTH or insufficient data.
    """
    if not rth_session_now():
        return None
    tkr = yf.Ticker(symbol)
    df = tkr.history(period="2d", interval="1m", prepost=True, actions=False, raise_errors=False)
    if df is None or df.empty:
        return None
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(NY)
    else:
        df.index = df.index.tz_convert(NY)
    df = df.rename(columns={c: c.capitalize() for c in df.columns})
    today = pd.Timestamp.now(NY).date()
    day = df.loc[df.index.date == today]
    if day.empty:
        return None
    rth = day.between_time("09:30","16:00")
    if rth.empty:
        return None
    typical = (rth["High"] + rth["Low"] + rth["Close"])/3.0
    pv = (typical * rth["Volume"]).cumsum()
    vv = rth["Volume"].cumsum().replace(0, np.nan)
    vwap = (pv / vv).iloc[-1]
    last = rth["Close"].iloc[-1]
    if vwap and vwap > 0:
        return float(((last - vwap) / vwap) * 10_000.0)
    return None
