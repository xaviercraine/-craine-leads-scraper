"""Filter comments down to those written in operator-mode (first-person, present/past tense).

Top-level posts bypass this entirely — title relevance is enough signal. Comments
need stricter filtering because the same keyword in a comment is much noisier
(philosophical takes, jokes, tangential mentions).
"""
import re

from . import config

# Operator language patterns: someone speaking from their own/team's experience.
# The pattern matches phrases like "we just finished", "our auditor", "I'm prepping",
# which strongly correlate with active SOC 2 buyer behavior.
OPERATOR_PATTERN = re.compile(
    r"\b("
    r"we|our team|our company|our auditor|"
    r"we're|we are|we just|we recently|we hired|we're hiring for|"
    r"i'm prepping|i just finished|"
    r"just went through|just finished"
    r")\b",
    re.IGNORECASE,
)


def passes_comment_filter(text: str, author_karma: int) -> bool:
    """Return True if the comment passes all gates for scoring.

    Gates (all must pass):
        - Length >= MIN_COMMENT_LEN (filters one-line quips)
        - Author karma >= MIN_AUTHOR_KARMA (filters brand-new throwaways)
        - Contains operator-language pattern
    """
    if not text or len(text) < config.MIN_COMMENT_LEN:
        return False
    if author_karma < config.MIN_AUTHOR_KARMA:
        return False
    if not OPERATOR_PATTERN.search(text):
        return False
    return True
