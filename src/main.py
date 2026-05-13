"""Weekly SOC 2 HN scrape — entrypoint.

Reads .last_run, queries HN Algolia for new hits since then, scores them,
dedupes against the sheet's existing rows, and batch-appends new ones.

Set DRY_RUN=true to skip sheet writes (used for manual test runs).
"""
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, hn_client, scoring, filters, dedup, sheets_client


LAST_RUN_PATH = Path(config.LAST_RUN_FILE)


def get_last_run_ts() -> int:
    """Read .last_run; if missing or unreadable, default to N days ago."""
    if LAST_RUN_PATH.exists():
        try:
            return int(LAST_RUN_PATH.read_text().strip())
        except (ValueError, OSError):
            pass
    fallback = int(time.time()) - (config.DEFAULT_LOOKBACK_DAYS * 86400)
    print(f"[main] No .last_run found, falling back to {config.DEFAULT_LOOKBACK_DAYS} days ago")
    return fallback


def write_last_run_ts(ts: int) -> None:
    LAST_RUN_PATH.write_text(str(ts))


def hit_to_row(source: str, hit: dict, score: float, matched_kws: list[str]) -> list:
    """Translate an HN Algolia hit into a sheet row matching config.HEADERS order.

    Scraper-owned columns (A-L) get populated here. Triage columns (M-R) are left
    blank for Claude to fill on Monday morning.
    """
    object_id = hit.get("objectID", "")
    author = hit.get("author", "")
    created_at_i = hit.get("created_at_i", 0)

    if source == "hn_comment":
        title = hit.get("story_title") or ""  # parent thread title
        snippet = (hit.get("comment_text") or "")[:500]
        url = f"https://news.ycombinator.com/item?id={object_id}"
        post_type = "comment"
    elif source == "hn_ask":
        title = hit.get("title") or ""
        snippet = (hit.get("story_text") or "")[:500]
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        post_type = "ask_hn"
    else:  # hn_story
        title = hit.get("title") or ""
        snippet = (hit.get("story_text") or "")[:500]
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        post_type = "story"

    posted_at = (
        datetime.fromtimestamp(created_at_i, tz=timezone.utc).isoformat()
        if created_at_i
        else ""
    )
    scraped_at = datetime.now(timezone.utc).isoformat()

    return [
        scraped_at,                              # A scraped_at
        source,                                  # B source
        object_id,                               # C source_item_id
        url,                                     # D source_url
        author,                                  # E author
        post_type,                               # F post_type
        posted_at,                               # G posted_at
        title,                                   # H title
        snippet,                                 # I snippet
        "|".join(matched_kws),                   # J matched_keywords
        round(score, 3),                         # K signal_strength
        dedup.dedup_hash(source, object_id),     # L dedup_hash
        "",                                      # M triage_status
        "",                                      # N triage_date
        "",                                      # O triage_notes
        "",                                      # P company_guess
        "",                                      # Q company_domain
        "",                                      # R notion_page_id
    ]


def run() -> None:
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    since_ts = get_last_run_ts()
    since_iso = datetime.fromtimestamp(since_ts, tz=timezone.utc).isoformat()
    print(f"[main] Scraping since unix={since_ts} ({since_iso})")
    print(f"[main] DRY_RUN={dry_run}")

    all_keywords = config.TIER_1_KEYWORDS + config.TIER_2_KEYWORDS + config.TIER_3_KEYWORDS

    # Cache karma lookups — same author may show up across many keywords/comments.
    karma_cache: dict[str, int] = {}

    def get_karma(author: str) -> int:
        if author not in karma_cache:
            karma_cache[author] = hn_client.get_user_karma(author)
        return karma_cache[author]

    # In-run dedup: same hit can match multiple keywords. We only want it once.
    seen_object_ids: set[str] = set()
    candidates: list[tuple[str, dict, float, list[str]]] = []

    # --- Stage 1: stories + Ask HN ---
    for _kw, _tag, hit in hn_client.fetch_all(all_keywords, ["story", "ask_hn"], since_ts):
        object_id = hit.get("objectID")
        if not object_id or object_id in seen_object_ids:
            continue
        author = hit.get("author", "")
        karma = get_karma(author)
        score, matched = scoring.score_story(hit, karma)
        if score < config.MIN_SIGNAL_STRENGTH:
            continue
        seen_object_ids.add(object_id)
        source = "hn_ask" if "ask_hn" in (hit.get("_tags") or []) else "hn_story"
        candidates.append((source, hit, score, matched))

    # --- Stage 2: comments (stricter filter) ---
    for _kw, _tag, hit in hn_client.fetch_all(all_keywords, ["comment"], since_ts):
        object_id = hit.get("objectID")
        if not object_id or object_id in seen_object_ids:
            continue
        text = hit.get("comment_text") or ""
        author = hit.get("author", "")
        karma = get_karma(author)
        if not filters.passes_comment_filter(text, karma):
            continue
        parent_title = hit.get("story_title") or ""
        score, matched = scoring.score_comment(hit, karma, parent_title)
        if score < config.MIN_SIGNAL_STRENGTH:
            continue
        seen_object_ids.add(object_id)
        candidates.append(("hn_comment", hit, score, matched))

    print(f"[main] {len(candidates)} candidates passing threshold")

    if not candidates:
        if not dry_run:
            write_last_run_ts(int(time.time()))
        print("[main] Nothing to write. Done.")
        return

    # --- Stage 3: dedup against the sheet and write ---
    if dry_run:
        ws = None
        existing_hashes: set[str] = set()
        print("[main] DRY_RUN: skipping sheet read, treating all candidates as new")
    else:
        ws = sheets_client.get_worksheet()
        if sheets_client.ensure_headers(ws):
            print("[main] Headers were missing/wrong; rewrote row 1")
        existing_hashes = sheets_client.get_existing_hashes(ws)
        print(f"[main] {len(existing_hashes)} existing rows in sheet (by hash)")

    rows_to_write: list[list] = []
    for source, hit, score, matched in candidates:
        row = hit_to_row(source, hit, score, matched)
        row_hash = row[11]  # column L
        if row_hash in existing_hashes:
            continue
        rows_to_write.append(row)

    print(f"[main] {len(rows_to_write)} new rows to write (after sheet-side dedup)")

    if dry_run:
        print("[main] DRY_RUN: would write these rows (showing first 5):")
        for row in rows_to_write[:5]:
            # Trim snippet for log readability.
            display = row[:8] + [row[8][:80] + "..."] + row[9:12]
            print(f"  {display}")
        if len(rows_to_write) > 5:
            print(f"  ... and {len(rows_to_write) - 5} more")
        return

    appended = sheets_client.append_rows(ws, rows_to_write)
    print(f"[main] Appended {appended} rows")

    write_last_run_ts(int(time.time()))
    print("[main] Done.")


if __name__ == "__main__":
    run()
