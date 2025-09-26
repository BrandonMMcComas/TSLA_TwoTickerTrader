from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

=======
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # pragma: no cover - optional dependency in tests
    from openai import OpenAI
except Exception:  # pragma: no cover - surface-friendly fallback
    OpenAI = None

VALID_CATS = {"company", "us_macro", "global_trade"}
SYS = "You are a financial news assistant. Return only valid JSON as instructed."
USER_TEMPLATE = (
    "Score the article and return strict JSON with keys: "
    "category in {company, us_macro, global_trade}, sentiment in [-1,1], "
    "relevance in [0,1], summary (<= 40 words).\n"
    "Title: {title}\nURL: {url}\nSource: {source}\n"
)

main

@dataclass
class ScoredItem:
    category: str
    sentiment: float
    relevance: float
    summary: str
    title: str
    url: str
    source: str
    published: float



VALID_CATS = {"company", "us_macro", "global_trade"}
SYS = "You are a financial news assistant. Return only valid JSON as instructed."
USER_TEMPLATE = (
    "Score the article and return strict JSON with keys: category in {company, us_macro, "
    "global_trade}, sentiment in [-1,1], relevance in [0,1], summary (<= 40 words).\n"
    "Title: {title}\nURL: {url}\nSource: {source}\n"
)


def score_articles_openai(
    items: List[Dict[str, Any]], api_key: Optional[str]
) -> List[ScoredItem]:
    out: List[ScoredItem] = []
=======
def score_articles_openai(items: List[Dict[str, Any]], api_key: Optional[str]) -> List[ScoredItem]:
    results: List[ScoredItem] = []
main
    if not api_key or OpenAI is None or not items:
        return results

    client = OpenAI(api_key=api_key)

    for it in items:
        title = it["title"]
        url = it["url"]
        source = it["source"]
        published = it["published"]
=======
    for item in items:
        title = str(item["title"])
        url = str(item["url"])
        source = str(item["source"])
        published = float(item["published"])
main
        content = USER_TEMPLATE.format(title=title, url=url, source=source)
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SYS},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_object"},
            )

            txt = resp.choices[0].message.content or "{}"
            data = json.loads(txt)
            cat = str(data.get("category", "")).strip().lower()
            if cat not in VALID_CATS:
                cat = "company" if "tesla" in title.lower() else "us_macro"
            sent = float(data.get("sentiment", 0.0))
            rel = float(data.get("relevance", 0.5))
            summ = str(data.get("summary", "")).strip()[:240]
            out.append(
                ScoredItem(
                    category=cat,
                    sentiment=max(-1, min(1, sent)),
                    relevance=max(0, min(1, rel)),
                    summary=summ,
                    title=title,
                    url=url,
                    source=source,
                    published=published,
                )
            )
        except Exception:
            continue
    return out


def aggregate_daily(scored: List[ScoredItem]):
    def wavg(vals: List[tuple[float, float]]):
        if not vals:
            return None
        s_num = sum(v * w for v, w in vals)
        s_den = sum(w for _, w in vals)
        return s_num / s_den if s_den > 0 else None

    cats: Dict[str, List[tuple[float, float]]] = {
=======
            text = response.choices[0].message.content or "{}"
            data = json.loads(text)
        except Exception:
            continue

        category = str(data.get("category", "")).strip().lower()
        if category not in VALID_CATS:
            category = "company" if "tesla" in title.lower() else "us_macro"
        sentiment = float(data.get("sentiment", 0.0))
        relevance = float(data.get("relevance", 0.5))
        summary = str(data.get("summary", "")).strip()[:240]

        results.append(
            ScoredItem(
                category=category,
                sentiment=max(-1.0, min(1.0, sentiment)),
                relevance=max(0.0, min(1.0, relevance)),
                summary=summary,
                title=title,
                url=url,
                source=source,
                published=published,
            )
        )

    return results


def _weighted_average(values: Iterable[Tuple[float, float]]) -> Optional[float]:
    values_list = list(values)
    if not values_list:
        return None

    numerator = sum(val * weight for val, weight in values_list)
    denominator = sum(weight for _, weight in values_list)
    if denominator <= 0:
        return None
    return numerator / denominator


def aggregate_daily(scored: List[ScoredItem]) -> Dict[str, Any]:
    category_buckets: Dict[str, List[Tuple[float, float]]] = {
main
        "company": [],
        "us_macro": [],
        "global_trade": [],
    }

    for s in scored:
        cats.get(s.category, cats["company"]).append(
            (s.sentiment, max(0.01, s.relevance))
        )
    daily = wavg([(s.sentiment, max(0.01, s.relevance)) for s in scored])
    cat_scores = {k: (wavg(v) if v else None) for k, v in cats.items()}
    return {"daily_score": daily, "category_scores": cat_scores}


def to_json_blob(scored: List[ScoredItem]):
    agg = aggregate_daily(scored)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **agg,
        "items": [s.__dict__ for s in scored],
=======

    for item in scored:
        category_buckets.setdefault(item.category, category_buckets["company"]).append(
            (item.sentiment, max(0.01, item.relevance))
        )

    daily_values = [(item.sentiment, max(0.01, item.relevance)) for item in scored]
    daily_score = _weighted_average(daily_values)
    category_scores = {
        name: _weighted_average(values) if values else None
        for name, values in category_buckets.items()
    }

    return {"daily_score": daily_score, "category_scores": category_scores}


def to_json_blob(scored: List[ScoredItem]) -> Dict[str, Any]:
    aggregate = aggregate_daily(scored)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **aggregate,
        "items": [item.__dict__ for item in scored],
main
    }
