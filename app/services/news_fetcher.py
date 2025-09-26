from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from typing import List

import feedparser
import requests

AM_QUERIES = [
    (
        '("Tesla" OR "TSLA") (premarket OR pre-market OR early trading OR analyst) '
        "site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:wsj.com"
    ),
    (
        "(premarket OR futures) (CPI OR PCE OR jobs OR payrolls OR claims OR Fed OR yields) "
        "site:reuters.com OR site:bloomberg.com OR site:cnbc.com"
    ),
    (
        '(EV OR lithium OR nickel OR battery OR tariffs OR shipping OR '
        'Suez OR Panama OR China OR EU) '
        '("Tesla" OR "TSLA" OR "electric vehicle") site:reuters.com OR site:bloomberg.com'
    ),
]
PM_QUERIES = [
    (
        '("Tesla" OR "TSLA") (after-hours OR postmarket OR earnings OR deliveries OR '
        'recall OR guidance OR margins OR NHTSA) site:reuters.com OR site:bloomberg.com '
        'OR site:cnbc.com OR site:wsj.com'
    ),
    (
        "(market wrap OR stocks close OR yields OR Fed OR dollar) (S&P OR Nasdaq OR Dow) "
        "site:reuters.com OR site:bloomberg.com OR site:cnbc.com"
    ),
    (
        "(Asia OR Europe OR oil OR Middle East OR tariffs OR shipping OR supply chain) "
        "(market OR stocks OR risk) site:reuters.com OR site:bloomberg.com"
    ),
]


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published: float


def _dedupe_by_url(items: List[NewsItem], cap: int) -> List[NewsItem]:
    seen = set()
    out: List[NewsItem] = []
    for it in sorted(items, key=lambda x: x.published, reverse=True):
        u = it.url.split("?")[0].rstrip("/")
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
        if len(out) >= cap:
            break
    return out


def _cse_query(
    q: str, key: str, cse_id: str, date_restrict: str = "d1"
) -> List[NewsItem]:
    endpoint = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": key,
        "cx": cse_id,
        "q": q,
        "dateRestrict": date_restrict,
        "num": 10,
        "sort": "date",
    }
    r = requests.get(endpoint, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    items: List[NewsItem] = []
    for it in data.get("items", []):
        link = it.get("link") or it.get("formattedUrl") or ""
        title = it.get("title") or ""
        ts = time.time()
        src = urllib.parse.urlparse(link).netloc
        items.append(NewsItem(title=title, url=link, source=src, published=ts))
    return items


def _rss_query(q: str) -> List[NewsItem]:
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(q)
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    feed = feedparser.parse(url)
    out: List[NewsItem] = []
    for e in feed.get("entries", []):
        link = e.get("link", "")
        title = e.get("title", "")
        ts = (
            time.mktime(e.published_parsed)
            if getattr(e, "published_parsed", None)
            else time.time()
        )
        src = urllib.parse.urlparse(link).netloc
        out.append(NewsItem(title=title, url=link, source=src, published=ts))
    return out


def fetch_news(
    am: bool, max_items: int, google_key: str | None, cse_id: str | None
) -> List[NewsItem]:
    queries = AM_QUERIES if am else PM_QUERIES
    items: List[NewsItem] = []
    for q in queries:
        try:
            if google_key and cse_id:
                items.extend(_cse_query(q, google_key, cse_id, "d1"))
            else:
                items.extend(_rss_query(q))
        except Exception:
            pass
    return _dedupe_by_url(items, cap=max_items)
