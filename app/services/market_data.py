# Placeholder shim for get_quote(symbol) used by trader.py if the real market_data
# service isn't present during initial import. Section 02 should have implemented this.
from datetime import datetime


def get_quote(symbol: str):
    return {
        "symbol": symbol,
        "bid": 100.0,
        "ask": 100.2,
        "last": 100.1,
        "ts": datetime.utcnow(),
    }
