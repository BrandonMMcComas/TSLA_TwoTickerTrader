
from typing import Literal, Tuple

Side = Literal["BUY", "SELL"]

def bps(x: float) -> float:
    return x / 10_000.0

def spread_bps(bid: float, ask: float) -> float:
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return 999999.0
    mid = (bid + ask) / 2.0
    return ((ask - bid) / mid) * 10_000.0

def compute_entry_limit(side: Side, bid: float, ask: float, last: float, slippage_bps: int) -> float:
    """
    BUY  = min(ask * (1 + slippage), last * (1 + slippage))
    SELL = max(bid * (1 - slippage), last * (1 - slippage))
    """
    s = bps(slippage_bps)
    if side == "BUY":
        return min(ask * (1 + s), last * (1 + s))
    else:
        return max(bid * (1 - s), last * (1 - s))

def compute_stop_limit(entry_avg: float, stop_loss_pct: float, limit_offset_bps: int) -> Tuple[float, float]:
    """
    stop_price = entry_avg * (1 - STOP_LOSS_PCT)
    limit_price = stop_price * (1 - STOP_LIMIT_OFFSET_BPS)
    """
    stop_price = entry_avg * (1 - stop_loss_pct)
    lim = stop_price * (1 - bps(limit_offset_bps))
    return round(stop_price, 4), round(lim, 4)
