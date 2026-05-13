"""Thin wrappers around HN Algolia search and HN Firebase user endpoints.

Both APIs are free, public, and unauthenticated. The Algolia endpoint is the
search index; the Firebase endpoint is the official HN data API and exposes
user karma which Algolia doesn't return.
"""
import time
from typing import Iterator

import requests

ALGOLIA_BASE = "https://hn.algolia.com/api/v1/search_by_date"
FIREBASE_USER = "https://hacker-news.firebaseio.com/v0/user/{username}.json"

# Be polite. 100ms between queries is plenty under HN Algolia's rate limits.
INTER_QUERY_SLEEP_S = 0.1


def search(keyword: str, tag: str, since_ts: int, hits_per_page: int = 100) -> list[dict]:
    """Single HN Algolia query. Returns raw hits.

    Args:
        keyword: search query, e.g. "SOC 2".
        tag: one of "story", "comment", "ask_hn", "show_hn".
        since_ts: unix timestamp; only return hits created after this.
        hits_per_page: max results to return (Algolia caps at 1000).

    Raises:
        requests.RequestException on network errors. Caller decides whether to swallow.
    """
    params = {
        "query": keyword,
        "tags": tag,
        "numericFilters": f"created_at_i>{since_ts}",
        "hitsPerPage": hits_per_page,
    }
    resp = requests.get(ALGOLIA_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def fetch_all(
    keywords: list[str],
    tags: list[str],
    since_ts: int,
) -> Iterator[tuple[str, str, dict]]:
    """Yield (keyword, tag, hit) for every match across the keyword x tag matrix.

    The caller is responsible for in-run dedup since the same hit can match
    multiple keywords (e.g. a post mentioning both "SOC 2" and "Vanta").
    """
    for keyword in keywords:
        for tag in tags:
            try:
                hits = search(keyword, tag, since_ts)
                print(f"[hn_client] keyword={keyword!r} tag={tag!r}: {len(hits)} hits")
                for hit in hits:
                    yield (keyword, tag, hit)
            except requests.RequestException as e:
                # Don't kill the whole run for one bad query.
                print(f"[hn_client] WARNING: query failed for keyword={keyword!r} tag={tag!r}: {e}")
                continue
            time.sleep(INTER_QUERY_SLEEP_S)


def get_user_karma(username: str) -> int:
    """Fetch a user's karma from HN's Firebase API. Returns 0 on any failure.

    HN Algolia returns the author username but not their karma; we need a
    separate roundtrip per unique author. Caller should cache results.
    """
    if not username:
        return 0
    try:
        resp = requests.get(FIREBASE_USER.format(username=username), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data is None:  # username doesn't exist
            return 0
        return int(data.get("karma", 0))
    except (requests.RequestException, ValueError, TypeError):
        return 0
