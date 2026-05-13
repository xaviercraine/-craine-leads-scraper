"""Single source of truth for keywords, thresholds, and the sheet schema."""

# --- Keyword tiers ---

# Tier 1: direct SOC 2 intent. Title hits get the strongest base score.
TIER_1_KEYWORDS = [
    "SOC 2",
    "SOC2",
    "SOC Type II",
    "SOC Type 2",
    "Type 2 audit",
    "Type II audit",
    "SOC report",
]

# Tier 2: adjacent compliance frameworks. Often coexist with or precede SOC 2.
TIER_2_KEYWORDS = [
    "ISO 27001",
    "HIPAA compliance",
    "compliance audit",
    "security audit",
    "GRC",
    "pen test report",
]

# Tier 3: competitor vendor names. In comments, mentions of these = displacement opportunity.
TIER_3_KEYWORDS = [
    "Vanta",
    "Drata",
    "Secureframe",
    "Sprinto",
    "Tugboat Logic",
    "Thoropass",
    "Hyperproof",
]


# --- Sheet schema ---
# This MUST match the row 1 in the Google Sheet exactly, in order.
# ensure_headers() in sheets_client uses this list as the canonical source.

HEADERS = [
    "scraped_at",         # A — UTC ISO timestamp when scraper found it
    "source",             # B — hn_story | hn_ask | hn_comment
    "source_item_id",     # C — HN Algolia objectID
    "source_url",         # D — direct link to the post or comment
    "author",             # E — HN username
    "post_type",          # F — story | ask_hn | comment
    "posted_at",          # G — UTC ISO timestamp of original post
    "title",              # H — post title (or parent thread title for comments)
    "snippet",            # I — first 500 chars of body/comment text
    "matched_keywords",   # J — pipe-delimited list of keywords that matched
    "signal_strength",    # K — float in [0, 1], scraper's score
    "dedup_hash",         # L — sha256(source|item_id)[:16] — idempotency key
    "triage_status",      # M — empty | promoted | skipped | deferred (Claude fills)
    "triage_date",        # N — UTC ISO when triaged
    "triage_notes",       # O — Claude's rationale and suggested angle
    "company_guess",      # P — inferred company name
    "company_domain",     # Q — inferred domain
    "notion_page_id",     # R — Notion page ID after promotion
]


# --- Thresholds ---

# Rows scoring below this are dropped, not written to the sheet.
MIN_SIGNAL_STRENGTH = 0.3

# Comment filter: must be at least this many chars and from a user with at least this much karma.
MIN_COMMENT_LEN = 100
MIN_AUTHOR_KARMA = 10

# Comments in this length window get a small score boost (substantive but not a manifesto).
COMMENT_LEN_SWEET_LOW = 200
COMMENT_LEN_SWEET_HIGH = 1500


# --- State ---

# File tracking the last successful run's unix timestamp.
# Committed back to the repo by the Actions workflow.
LAST_RUN_FILE = ".last_run"

# If .last_run is missing (first run), look back this many days.
DEFAULT_LOOKBACK_DAYS = 7
