from __future__ import annotations
from typing import Optional
from datetime import datetime
import pytz, os, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config.settings import (SENTIMENT_AM_ET, SENTIMENT_PM_ET, TIMEZONE,
                                 SENTIMENT_MAX_ITEMS, SENTIMENT_RETENTION_DAYS,
                                 SENTIMENT_SKIP_WEEKENDS)
from app.config.paths import DATA_DIR
from app.core.usb_guard import read_keys_env
from app.services.news_fetcher import fetch_news
from app.services.sentiment import score_articles_openai, to_json_blob
_TZ = pytz.timezone(TIMEZONE)
_sched: Optional[BackgroundScheduler] = None
_last_run_iso: Optional[str] = None
def _sentiment_job(usb_path: str):
    global _last_run_iso
    now_et = datetime.now(_TZ)
    if SENTIMENT_SKIP_WEEKENDS and now_et.weekday() >= 5:
        _last_run_iso = now_et.isoformat()
        return
    ok, _ = read_keys_env(usb_path)
    vals = {}
    if ok:
        from dotenv import dotenv_values
        vals = dotenv_values(os.path.join(usb_path, "keys.env")) or {}
    news = fetch_news(am=(now_et.hour < 12), max_items=SENTIMENT_MAX_ITEMS,
                      google_key=vals.get("GOOGLE_API_KEY"), cse_id=vals.get("GOOGLE_CSE_ID"))
    items = [ {"title": n.title, "url": n.url, "source": n.source, "published": n.published} for n in news ]
    scored = score_articles_openai(items, api_key=vals.get("OPENAI_API_KEY"))
    blob = to_json_blob(scored)
    outdir = DATA_DIR / "sentiment"; outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{now_et.date().isoformat()}.json"
    with open(path, "w", encoding="utf-8") as f:
        import json; json.dump(blob, f, ensure_ascii=False, indent=2)
    _prune_old(outdir, keep_days=SENTIMENT_RETENTION_DAYS)
    _last_run_iso = now_et.isoformat()
def _prune_old(folder, keep_days: int):
    horizon = time.time() - keep_days * 86400
    for p in folder.glob("*.json"):
        try:
            if p.stat().st_mtime < horizon: p.unlink(missing_ok=True)
        except Exception:
            pass
def start_scheduler(usb_path: str) -> None:
    global _sched
    if _sched is not None: return
    _sched = BackgroundScheduler(timezone=_TZ)
    am_h, am_m = map(int, SENTIMENT_AM_ET.split(":"))
    pm_h, pm_m = map(int, SENTIMENT_PM_ET.split(":"))
    _sched.add_job(_sentiment_job, CronTrigger(hour=am_h, minute=am_m), args=[usb_path], id="sentiment_am", replace_existing=True)
    _sched.add_job(_sentiment_job, CronTrigger(hour=pm_h, minute=pm_m), args=[usb_path], id="sentiment_pm", replace_existing=True)
    _sched.start()
def get_last_sentiment_run_iso() -> Optional[str]:
    return _last_run_iso
