from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, List

import feedparser
import requests

AM_QUERIES = [
    '("Tesla" OR "TSLA") (premarket OR pre-market OR early trading OR analyst) site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:wsj.com',
    '(premarket OR futures) (CPI OR PCE OR jobs OR payrolls OR claims OR Fed OR yields) site:reuters.com OR site:bloomberg.com OR site:cnbc.com',
    '(EV OR lithium OR nickel OR battery OR tariffs OR shipping OR Suez OR Panama OR China OR EU) ("Tesla" OR "TSLA" OR "electric vehicle") site:reuters.com OR site:bloomberg.com',
]

PM_QUERIES = [
    '("Tesla" OR "TSLA") (after-hours OR postmarket OR earnings OR deliveries OR recall OR guidance OR margins OR NHTSA) site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:wsj.com',
    '(market wrap OR stocks close OR yields OR Fed OR dollar) (S&P OR Nasdaq OR Dow) site:reuters.com OR site:bloomberg.com OR site:cnbc.com',
    '(Asia OR Europe OR oil OR Middle East OR tariffs OR shipping OR supply chain) (market OR stocks OR risk) site:reuters.com OR site:bloomberg.com',
]


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published: float


def _dedupe_by_url(items: Iterable[NewsItem], cap: int) -> List[NewsItem]:
    seen: set[str] = set()
    deduped: List[NewsItem] = []
    for item in sorted(items, key=lambda x: x.published, reverse=True):
        url = item.url.split("?")[0].rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        deduped.append(item)
        if len(deduped) >= cap:
            break
    return deduped


def _cse_query(query: str, key: str, cse_id: str, date_restrict: str = "d1") -> List[NewsItem]:
    endpoint = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": key,
        "cx": cse_id,
        "q": query,
        "dateRestrict": date_restrict,
        "num": 10,
        "sort": "date",
    }
    response = requests.get(endpoint, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()

    items: List[NewsItem] = []
    for entry in payload.get("items", []):
        link = entry.get("link") or entry.get("formattedUrl") or ""
        title = entry.get("title") or ""
        timestamp = time.time()
        source = urllib.parse.urlparse(link).netloc
        items.append(NewsItem(title=title, url=link, source=source, published=timestamp))
    return items


def _rss_query(query: str) -> List[NewsItem]:
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)

    items: List[NewsItem] = []
    for entry in feed.get("entries", []):
        link = entry.get("link", "")
        title = entry.get("title", "")
        timestamp = (
            time.mktime(entry.published_parsed)
            if getattr(entry, "published_parsed", None)
            else time.time()
        )
        source = urllib.parse.urlparse(link).netloc
        items.append(NewsItem(title=title, url=link, source=source, published=timestamp))
    return items


def fetch_news(am: bool, max_items: int, google_key: str | None, cse_id: str | None) -> List[NewsItem]:
    queries = AM_QUERIES if am else PM_QUERIES
    items: List[NewsItem] = []
    use_cse = bool(google_key and cse_id)

    for query in queries:
        try:
            if use_cse:
                assert google_key is not None and cse_id is not None
                items.extend(_cse_query(query, google_key, cse_id, "d1"))
            else:
                items.extend(_rss_query(query))
        except Exception:
            continue

    return _dedupe_by_url(items, cap=max_items)
