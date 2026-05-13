"""Stable hash function for deduplicating rows across runs.

The hash goes into column L of the sheet. On each run, the scraper reads
all existing hashes from column L and skips any candidate whose hash already
appears. This means re-running the scraper is safe and idempotent.
"""
import hashlib


def dedup_hash(source: str, item_id: str) -> str:
    """Stable 16-char hex hash for (source, item_id).

    Args:
        source: "hn_story", "hn_ask", or "hn_comment".
        item_id: HN Algolia objectID.

    Returns:
        16-char hex string. Collision probability is ~1 in 10^19 at expected scale.
    """
    payload = f"{source}|{item_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
