
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

## GUI at a glance

- **Dashboard** — decision engine card with p_up, sentiment blend, conviction, side badge, spread/VWAP flags, sparkline history, session badges, account tiles (equity, cash, position, P&L), and quick links to review the latest trade in the logs.
- **Trading** — live TSLL/TSDD quote snapshots, conviction-scaled cash allocation preview, flip cooldown countdown, and engine enable/disable toasts.
- **Settings** — USB key management plus live sliders for gate threshold, blend weights, coinflip buffer, spread guardrails, flip cooldown, session toggles, and appearance preferences with dark mode + font sizing persisted to `data/ui_state.json`.
- **Logs** — filterable log tail (level, contains text, since time) with pretty-printed decision components and recent trades.
- **Train** — non-blocking training launcher with dataset status, progress indicator, and metric summary.

### Keyboard shortcuts

- `Ctrl+D` — Dashboard
- `Ctrl+T` — Trading
- `Ctrl+S` — Settings
- `Ctrl+L` — Logs
- `Ctrl+R` — Train

### Build an EXE (Windows)
```
.uild_exe.cmd
```
Output: `.\dist\TSLA Two-Ticker Trader\TSLA Two-Ticker Trader.exe`

### Logs & Data
- Logs → `logs/app.log`
- Trades CSV → `data/trades.csv`
- Sentiment JSONs → `data/sentiment/YYYY-MM-DD.json`
