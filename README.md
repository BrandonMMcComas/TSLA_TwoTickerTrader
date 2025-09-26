
# TSLA Two-Ticker Trader

This archive contains Section 04 deliverables — Trading Engine (Limit-only), Pricing helper, and Alpaca client wrapper.

**Highlights**
- Live trading only (never paper).
- Limit-only entries/exits with extended-hours emulated FOK.
- Cash-only sizing using *non_marginable_buying_power* (proxy for settled cash).
- Protective stop-limit (2.5%) and P80 take-profit.
- Replace throttle & spread guard.
- One-position policy: TSLL (if up) or TSDD (if down), with flip flow.

See `app/services/trader.py`, `app/services/pricing.py`, and `app/services/alpaca_client.py` for implementation details.


---

## Section 05 — GUI Polish, Shortcuts & Icon

### Dashboard
- **Trade Gate tile** (green/red) shows p_up / p_blend vs threshold and blocking conditions.
- **Sparklines**: p_up (last 60), TSLL spread (bps), TSDD spread (bps).
- **Session pills** & **Extended Hours OK** banner when Pre/After active in-session.
- **PDT/Cash pill** based on Alpaca account snapshot.
- **Last sentiment run** time (from `data/sentiment/` file timestamp).

### Settings
- **USB keys** writer (USB-only).
- **Gate threshold** slider (0.40–0.70).
- **Blend weights** (w_model, w_sent) with **Normalize** button.
- **Session toggles** & **Risk/price controls** (in-memory only; not persisted to disk).
- **Create Desktop Shortcut** — `TSLA Two-Ticker Trader.lnk` with icon.

### Trade Control
- **Start/Stop** (in-memory flag for now; full engine wiring occurs alongside Section 04 backend).
- **Account snapshot** (equity, settled cash), **holding**, and **chosen limit preview**.

> Per guardrails, only the **USB path** is persisted locally. Keys live only on the USB; other settings are in-memory for the session.


### Dashboard — new tiles
- **TSLA last trade** (auto-updates).
- **VWAP distance (RTH)** — live basis-point distance of price vs session VWAP.


---

## Section 06 — QA, Packaging & Final ZIP (+ EXE spec)
- Verified imports with `tests/test_imports.py` and basic GUI launch.
- Provided **PyInstaller spec** (`tsla_trader.spec`) with `console=True` and icon; convenience **build_exe.cmd** script.
- Final **start_app.cmd** launches GUI with console visible.
- Dashboard now includes **TSLA last trade** and **VWAP distance (RTH)** tiles.

### Build an EXE (Windows)
```
.uild_exe.cmd
```
Output: `.\dist\TSLA Two-Ticker Trader\TSLA Two-Ticker Trader.exe`

### Logs & Data
- Logs → `logs/app.log`
- Trades CSV → `data/trades.csv`
- Sentiment JSONs → `data/sentiment/YYYY-MM-DD.json`
