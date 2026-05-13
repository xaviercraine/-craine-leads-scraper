"""Signal strength scoring for HN hits.

Design philosophy: linear weighted sum, clamped to [0, 1], no sigmoid.
The score is meant to be debuggable — if a row's score feels wrong, you
should be able to look at the weights and explain it.
"""
from . import config


def matched_keywords_in_text(text: str, keyword_list: list[str]) -> list[str]:
    """Return keywords from keyword_list that appear in text (case-insensitive)."""
    if not text:
        return []
    text_lower = text.lower()
    return [kw for kw in keyword_list if kw.lower() in text_lower]


def score_story(hit: dict, author_karma: int) -> tuple[float, list[str]]:
    """Score a top-level story or Ask HN post.

    Returns:
        (signal_strength in [0, 1], list of unique matched keywords)
    """
    title = hit.get("title") or ""
    body = hit.get("story_text") or ""
    tags = hit.get("_tags", []) or []

    tier1_in_title = matched_keywords_in_text(title, config.TIER_1_KEYWORDS)
    tier1_in_body = matched_keywords_in_text(body, config.TIER_1_KEYWORDS)
    tier2 = matched_keywords_in_text(title + " " + body, config.TIER_2_KEYWORDS)

    score = 0.0
    # Tier 1 in title is stronger signal than tier 1 in body. Use "or" — don't double-count.
    if tier1_in_title:
        score += 0.5
    elif tier1_in_body:
        score += 0.3
    if tier2:
        score += 0.2
    if "ask_hn" in tags:
        score += 0.2
    if author_karma > 500:
        score += 0.15
    if hit.get("num_comments", 0) > 5:
        score += 0.1

    score = min(1.0, score)
    matched = list(dict.fromkeys(tier1_in_title + tier1_in_body + tier2))  # preserve order, dedupe
    return score, matched


def score_comment(hit: dict, author_karma: int, parent_title: str = "") -> tuple[float, list[str]]:
    """Score a comment. Caller should have already passed the operator-language filter.

    Returns:
        (signal_strength in [0, 1], list of unique matched keywords)
    """
    text = hit.get("comment_text") or ""

    tier1 = matched_keywords_in_text(text, config.TIER_1_KEYWORDS)
    tier3 = matched_keywords_in_text(text, config.TIER_3_KEYWORDS)
    tier1_in_parent = matched_keywords_in_text(parent_title, config.TIER_1_KEYWORDS)

    score = 0.0
    if tier1:
        score += 0.4
    if tier3:
        # Competitor mention in a comment = displacement angle. Strong signal.
        score += 0.3
    if tier1_in_parent:
        # Cross-context boost: comment in a thread about SOC 2.
        score += 0.2
    text_len = len(text)
    if config.COMMENT_LEN_SWEET_LOW <= text_len <= config.COMMENT_LEN_SWEET_HIGH:
        score += 0.15
    if author_karma > 500:
        score += 0.15

    score = min(1.0, score)
    matched = list(dict.fromkeys(tier1 + tier3 + tier1_in_parent))
    return score, matched
