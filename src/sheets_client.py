"""Google Sheets I/O layer.

Authenticates via the GOOGLE_SERVICE_ACCOUNT_JSON env var (full keyfile JSON
as a string) and operates on the sheet identified by SHEET_ID.

All operations target the first worksheet (`sheet1`). The schema is owned
by config.HEADERS and enforced by ensure_headers().
"""
import json
import os

import gspread
from google.oauth2.service_account import Credentials

from . import config

# Scope just for Sheets — we don't need Drive-level access.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_worksheet():
    """Authenticate via service account JSON in env, return first worksheet."""
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    sheet_id = os.environ["SHEET_ID"]
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sheet_id)
    return sh.sheet1


def ensure_headers(ws) -> bool:
    """Read row 1; if it doesn't exactly match config.HEADERS, overwrite.

    Returns:
        True if row 1 was rewritten, False if it was already correct.
    """
    current = ws.row_values(1)
    if current == config.HEADERS:
        return False

    last_col_letter = _column_letter(len(config.HEADERS))
    range_name = f"A1:{last_col_letter}1"
    ws.update(range_name=range_name, values=[config.HEADERS])

    # Bold the header row. Best-effort; not all gspread versions/sheets support format().
    try:
        ws.format(range_name, {"textFormat": {"bold": True}})
    except Exception as e:
        print(f"[sheets_client] WARNING: could not bold headers: {e}")

    return True


def get_existing_hashes(ws) -> set[str]:
    """Read column L (dedup_hash) and return as a set, skipping the header row."""
    # Column L is index 12 (1-indexed in gspread).
    col_values = ws.col_values(12)
    if len(col_values) <= 1:
        return set()
    return set(v for v in col_values[1:] if v)


def append_rows(ws, rows: list[list]) -> int:
    """Batch-append rows to the sheet. Returns number appended."""
    if not rows:
        return 0
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def _column_letter(n: int) -> str:
    """1 -> A, 18 -> R, 27 -> AA. Used to build header range dynamically."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result
