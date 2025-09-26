"""
Unified settings module (Hotfix v1.4.1)

- Fix dataclass mutable defaults using default_factory
- Unify naming across Sections 03–06:
    * DEFAULT_USB_KEYS_PATH (Section 03) and DEFAULT_KEYS_USB_PATH (Section 04)
      -> both exported, same value
    * TIMEZONE (Section 03) and TZ (Section 04) -> both exported, same value
    * Keep legacy constants for compatibility; add aliases where helpful
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---- App metadata ----
@dataclass(frozen=True)
class AppInfo:
    name: str = "TSLA Two-Ticker Trader"
    version: str = "1.4.1"  # hotfix
    description: str = "Final integrated build with GUI & trading engine"


APP_INFO = AppInfo()

# ---- USB & secrets ----
DEFAULT_USB_KEYS_PATH = r"D:\SWINGBOT_KEYS"
DEFAULT_KEYS_USB_PATH = DEFAULT_USB_KEYS_PATH  # alias for Section 04 code
KEYS_ENV_FILENAME = "keys.env"

# ---- Timezone ----
TIMEZONE = "America/New_York"
TZ = TIMEZONE  # alias

# ---- Symbols & mapping ----
TICKERS = {"BASE": "TSLA", "UP": "TSLL", "DOWN": "TSDD"}
TSLA_SYMBOL = "TSLA"
TSLL_SYMBOL = "TSLL"
TSDD_SYMBOL = "TSDD"

# ---- Risk/pricing policy ----
SLIPPAGE_BPS = 30
SPREAD_MAX_BPS = 75
STOP_LOSS_PCT = 0.025
STOP_LIMIT_OFFSET_BPS = 10

# (Section 04 naming)
SLIPPAGE_BPS_DEFAULT = SLIPPAGE_BPS
SPREAD_MAX_BPS_DEFAULT = SPREAD_MAX_BPS
STOP_LOSS_PCT_DEFAULT = STOP_LOSS_PCT
STOP_LIMIT_OFFSET_BPS_DEFAULT = STOP_LIMIT_OFFSET_BPS

REPLACE_MIN_BPS_MOVE = 15
REPLACE_MIN_SECONDS = 2.5
REPLACE_MAX_COUNT = 10
REPLACE_COOLDOWN_RANGE_S = (10, 20)

# ---- FOK-like (extended hours) ----
FOK_WINDOW_MS = 800
FOK_MAX_WINDOWS = 3

# ---- Sessions ----
SESSION_PRE = True
SESSION_RTH = True
SESSION_AFTER = False

# ---- Gate & fusion ----
GATE_THRESHOLD_DEFAULT = 0.55
BLEND_W_MODEL = 0.70
BLEND_W_SENT = 0.30

# ---- Sentiment scheduling / retention ----
SENTIMENT_AM_ET = "06:00"
SENTIMENT_PM_ET = "18:00"
SENTIMENT_MAX_ITEMS = 12
SENTIMENT_RETENTION_DAYS = 30
SENTIMENT_SKIP_WEEKENDS = True

# ---- App info aliases for Section 04 code ----
APP_NAME = APP_INFO.name
APP_VERSION = APP_INFO.version


# ---- Structured settings objects (used by trading engine) ----
@dataclass
class SessionToggles:
    pre: bool = SESSION_PRE
    rth: bool = SESSION_RTH
    after: bool = SESSION_AFTER


@dataclass
class RiskSettings:
    stop_loss_pct: float = STOP_LOSS_PCT
    stop_limit_offset_bps: int = STOP_LIMIT_OFFSET_BPS
    slippage_bps: int = SLIPPAGE_BPS
    spread_max_bps: int = SPREAD_MAX_BPS
    replace_bps_threshold: int = REPLACE_MIN_BPS_MOVE
    replace_min_interval_sec: float = REPLACE_MIN_SECONDS
    replace_max_count: int = REPLACE_MAX_COUNT
    replace_cooldown_sec: tuple = REPLACE_COOLDOWN_RANGE_S
    fok_window_ms: int = FOK_WINDOW_MS
    fok_max_windows: int = FOK_MAX_WINDOWS


@dataclass
class TradingDefaults:
    session: SessionToggles = field(
        default_factory=SessionToggles
    )  # FIX: use default_factory
    risk: RiskSettings = field(default_factory=RiskSettings)  # FIX: use default_factory
    gate_threshold: float = GATE_THRESHOLD_DEFAULT


# Back-compat exports
PBLEND_THRESHOLD_DEFAULT = GATE_THRESHOLD_DEFAULT
LIVE_TRADING_ONLY = True  # enforce TradingClient(paper=False)
ONE_POSITION_ONLY = True
