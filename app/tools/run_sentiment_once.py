from __future__ import annotations
"""
app.tools.run_sentiment_once
Manual AM/PM sentiment run:
- Uses Google CSE (if GOOGLE_API_KEY + GOOGLE_CSE_ID exist); otherwise falls back to Google News RSS.
- Summarizes/scorers via OpenAI (gpt-4o-mini) into strict JSON items.
- Writes data/sentiment/YYYY-MM-DD.json and prunes >30 days.
Guardrails respected (USB-only secrets).

Usage:
  python -m app.tools.run_sentiment_once --am
  python -m app.tools.run_sentiment_once --pm
  python -m app.tools.run_sentiment_once --auto        # choose AM before noon ET, else PM
  python -m app.tools.run_sentiment_once --am --keep-weekends

Exit codes: 0 success, 2 missing OpenAI key, 3 network/API error, 4 other error.
"""
import sys, os, json, time, argparse, datetime, hashlib
from typing import List, Dict, Any, Tuple
import pytz
import requests
import feedparser
from openai import OpenAI
from app.config.paths import DATA_DIR
from app.core.app_config import AppConfig
from app.core.usb_guard import get_keys_dict
from pathlib import Path

NY = pytz.timezone("America/New_York")

AM_QUERIES = [
    # 1) Company Premarket
    '("Tesla" OR "TSLA") (premarket OR pre-market OR early trading OR analyst) site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:wsj.com',
    # 2) US Macro Today
    '(premarket OR futures) (CPI OR PCE OR jobs OR payrolls OR claims OR Fed OR yields) site:reuters.com OR site:bloomberg.com OR site:cnbc.com',
    # 3) Global Trade/Supply
    '(EV OR lithium OR nickel OR battery OR tariffs OR shipping OR Suez OR Panama OR China OR EU) ("Tesla" OR "TSLA" OR "electric vehicle") site:reuters.com OR site:bloomberg.com',
]
PM_QUERIES = [
    # 1) Company Post‑Market
    '("Tesla" OR "TSLA") (after-hours OR postmarket OR earnings OR deliveries OR recall OR guidance OR margins OR NHTSA) site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:wsj.com',
    # 2) US Macro Close Wrap
    '(market wrap OR stocks close OR yields OR Fed OR dollar) (S&P OR Nasdaq OR Dow) site:reuters.com OR site:bloomberg.com OR site:cnbc.com',
    # 3) Global Overnight Risk
    '(Asia OR Europe OR oil OR Middle East OR tariffs OR shipping OR supply chain) (market OR stocks OR risk) site:reuters.com OR site:bloomberg.com',
]

def _today_path() -> Path:
    outdir = DATA_DIR / "sentiment"
    outdir.mkdir(parents=True, exist_ok=True)
    day = datetime.datetime.now(NY).date().isoformat()
    return outdir / f"{day}.json"

def _prune_old(days: int = 30):
    outdir = DATA_DIR / "sentiment"
    if not outdir.exists():
        return
    now = datetime.datetime.now(NY).date()
    for p in outdir.glob("*.json"):
        try:
            d = datetime.date.fromisoformat(p.stem)
            if (now - d).days > days:
                p.unlink(missing_ok=True)
        except Exception:
            continue

def _dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set(); out = []
    for it in items:
        u = it.get("url") or it.get("link") or ""
        h = hashlib.sha256(u.encode("utf-8")).hexdigest() if u else None
        if h and h in seen:
            continue
        if h: seen.add(h)
        out.append(it)
    return out

def _google_cse_search(queries: List[str], key: str, cse_id: str) -> List[Dict[str, Any]]:
    # dateRestrict= d1 (last 1 day), sort by date
    base = "https://www.googleapis.com/customsearch/v1"
    results = []
    for q in queries:
        params = {"key": key, "cx": cse_id, "q": q, "sort": "date", "dateRestrict": "d1", "num": 10}
        r = requests.get(base, params=params, timeout=15)
        r.raise_for_status()
        js = r.json()
        for it in js.get("items", []):
            results.append({
                "title": it.get("title"),
                "snippet": it.get("snippet"),
                "url": it.get("link"),
                "source": "cse",
            })
    return _dedupe_by_url(results)

def _google_news_rss(queries: List[str]) -> List[Dict[str, Any]]:
    # Fallback only when no CSE keys. Use News RSS search with site: qualifiers
    results = []
    for q in queries:
        url = "https://news.google.com/rss/search"
        params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        feed = feedparser.parse(url, params=params)
        for e in feed.entries[:10]:
            results.append({
                "title": e.get("title"),
                "snippet": e.get("summary", ""),
                "url": e.get("link"),
                "source": "rss",
            })
    return _dedupe_by_url(results)

def _summarize_items(items: List[Dict[str, Any]], client: OpenAI, run_kind: str) -> Tuple[float, Dict[str,float], List[Dict[str, Any]]]:
    # limit to 12 newest-first (we already sorted by freshness via API; keep order)
    items = items[:12]
    out_items = []
    cats = {"company": [], "us_macro": [], "global_trade": []}

    sys_prompt = (
        "You are a market news summarizer for TSLA swing trading. "
        "Return STRICT JSON for each input article with fields: "
        "{category ∈ {company, us_macro, global_trade}, sentiment ∈ [-1,1], relevance ∈ [0,1], summary ≤ 40 words}."
    )
    for it in items:
        text = f"Title: {it.get('title')}\nSnippet: {it.get('snippet')}\nURL: {it.get('url')}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role":"system", "content": sys_prompt},
                {"role":"user", "content": f"Classify and summarize this article for the {run_kind.upper()} set:\n{text}\nReturn ONLY JSON object."}
            ]
        )
        content = resp.choices[0].message.content.strip()
        # Try to parse a single JSON object; if it fails, fallback to neutral
        try:
            js = json.loads(content)
            category = js.get("category")
            if category not in ("company","us_macro","global_trade"):
                category = "company"
            sentiment = float(js.get("sentiment", 0.0))
            sentiment = max(-1.0, min(1.0, sentiment))
            relevance = float(js.get("relevance", 0.0))
            relevance = max(0.0, min(1.0, relevance))
            summary = js.get("summary","")[:280]
        except Exception:
            category = "company"; sentiment = 0.0; relevance = 0.0; summary = "Neutral (parser fallback)."

        out = {
            "category": category,
            "sentiment": sentiment,
            "relevance": relevance,
            "summary": summary,
            "title": it.get("title"),
            "url": it.get("url"),
            "source": it.get("source"),
        }
        out_items.append(out)
        cats[category].append(sentiment * relevance)

    def wavg(vals: list[float]) -> float:
        if not vals: return 0.0
        # already weighted by relevance; average them
        return sum(vals) / max(1, len(vals))

    category_scores = {
        "company": round(wavg(cats["company"]), 4),
        "us_macro": round(wavg(cats["us_macro"]), 4),
        "global_trade": round(wavg(cats["global_trade"]), 4),
    }
    # daily_score = mean of three categories
    daily_score = round((category_scores["company"] + category_scores["us_macro"] + category_scores["global_trade"]) / 3.0, 4)
    return daily_score, category_scores, out_items

def run_once(run_kind: str, keep_weekends: bool) -> Path:
    # weekend skip
    today = datetime.datetime.now(NY).date()
    if not keep_weekends and today.weekday() >= 5:
        raise SystemExit("Weekend skip is ON. To override, pass --keep-weekends.")

    # config + keys
    cfg = AppConfig.load()
    keys = get_keys_dict(cfg.usb_keys_path)
    openai_key = keys.get("OPENAI_API_KEY", "")
    google_key = keys.get("GOOGLE_API_KEY", "")
    cse_id = keys.get("GOOGLE_CSE_ID", "")

    if not openai_key:
        sys.stderr.write("Missing OPENAI_API_KEY in USB keys.env\n")
        sys.exit(2)

    client = OpenAI(api_key=openai_key)

    # fetch
    queries = AM_QUERIES if run_kind == "am" else PM_QUERIES
    if google_key and cse_id:
        items = _google_cse_search(queries, google_key, cse_id)
    else:
        items = _google_news_rss(queries)

    # summarize/score
    daily, cats, out_items = _summarize_items(items, client, run_kind)

    # write JSON (atomic)
    out = {
        "daily_score": daily,
        "category_scores": cats,
        "updated_at": datetime.datetime.now(NY).isoformat(),
        "items": out_items,
        "run_kind": run_kind,
    }
    p = _today_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    os.replace(tmp, p)

    # prune
    _prune_old(30)
    return p

def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--am", action="store_true", help="Run AM query set now")
    g.add_argument("--pm", action="store_true", help="Run PM query set now")
    g.add_argument("--auto", action="store_true", help="Choose AM before 12:00 ET else PM")
    ap.add_argument("--keep-weekends", action="store_true", help="Do not skip on Sat/Sun")
    args = ap.parse_args(argv)

    if args.auto or (not args.am and not args.pm):
        hour = datetime.datetime.now(NY).hour
        run_kind = "am" if hour < 12 else "pm"
    else:
        run_kind = "am" if args.am else "pm"

    try:
        p = run_once(run_kind, keep_weekends=args.keep_weekends)
        print(f"Sentiment {run_kind.upper()} complete → {p}")
        return 0
    except SystemExit as e:
        print(str(e))
        return 0
    except requests.RequestException as e:
        sys.stderr.write(f"Network/API error: {e}\n")
        return 3
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 4

if __name__ == "__main__":
    raise SystemExit(main())
