# Craine Leads Scraper

Weekly Hacker News scraper for SOC 2 buyer-intent signals. Runs on GitHub Actions, writes hits into a Google Sheet, where Claude triages them every Monday morning.

## Architecture

- **Trigger:** GitHub Actions cron, Monday 12:00 UTC (8am ET).
- **Source:** HN Algolia free search API (no auth).
- **Targets:** Stories, Ask HN posts, and comments matching SOC 2 / compliance / competitor keywords.
- **Filtering:** Comments require operator-language pattern + author karma threshold.
- **Scoring:** Weighted `signal_strength` in `[0, 1]`; rows under `0.3` are dropped.
- **Output:** Append-only rows in the Google Sheet, deduped against column L.

## File layout

```
src/
├── main.py           entrypoint, wires everything together
├── config.py         keywords, thresholds, sheet schema
├── hn_client.py      HN Algolia API wrapper
├── scoring.py        signal_strength calculation
├── filters.py        operator-language filter for comments
├── dedup.py          stable hash for dedup
└── sheets_client.py  gspread wrapper, ensure_headers, append_rows

.github/workflows/
└── weekly-scrape.yml
```

## Setup (one-time)

Already done if you've followed the walk-through:

1. GCP project with Sheets API enabled.
2. Service account `soc2-scraper-bot@soc2-scraper-496214.iam.gserviceaccount.com` with a JSON key.
3. Target sheet shared with that service account email as **Editor**.
4. GitHub Secrets in this repo:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — full contents of the keyfile.
   - `SHEET_ID` — `1B-_I-jf4iLHK4N-RAKllZqUBE8iBXP7QGoFMMbIngOM`.

## First run (dry run)

Before letting the cron take over, test with a manual dry run:

1. GitHub repo → **Actions** tab → "Weekly SOC 2 HN Scrape" workflow.
2. Click **Run workflow**.
3. Set the `dry_run` input to `true`.
4. Click the green **Run workflow** to confirm.
5. Open the running job, watch the log. You'll see: candidate count, sample rows logged. No sheet writes happen in dry run.

If the log looks sane, run again with `dry_run` = `false`. Check the sheet — rows should appear below the headers.

## Then let it ride

The cron takes over from Monday morning onward. Each Monday around 8am ET the workflow runs, appends new rows, commits an updated `.last_run` timestamp back to the repo so the next run resumes from there.

## Triage loop (your weekly habit)

Every Monday after the scraper runs:

1. Open the sheet.
2. Open a Claude chat.
3. Ask Claude to read new rows where `triage_status` is empty and decide promote/skip/defer for each.
4. Claude writes decisions into columns M–O, attribution into P–Q, and pushes winners to Notion Leads (raw), writing the Notion page ID back into column R.
5. Tuesday–Friday, work the Notion list for outreach.

## Debugging

- **Permission denied on sheet:** verify the service account email is shared as Editor on the sheet, and that the `SHEET_ID` secret matches the sheet URL.
- **No candidates found:** check `.last_run` — if it's recent, there may genuinely be nothing new. Delete `.last_run` and re-run to force a 7-day lookback.
- **Auth errors:** the JSON in `GOOGLE_SERVICE_ACCOUNT_JSON` must be the complete file contents, including curly braces. Re-paste if in doubt.
- **HN Algolia 429s:** the script sleeps 100 ms between queries; if you hit limits anyway, raise the sleep in `hn_client.fetch_all`.

## Configuration knobs

In `src/config.py`:

- `TIER_1/2/3_KEYWORDS` — what to search for. Tier 1 is direct intent, Tier 2 is adjacent compliance, Tier 3 is competitor vendor names.
- `MIN_SIGNAL_STRENGTH` — drop threshold (default `0.3`).
- `MIN_COMMENT_LEN` / `MIN_AUTHOR_KARMA` — comment filter strictness.
- `DEFAULT_LOOKBACK_DAYS` — fallback lookback if no `.last_run` exists (default `7`).

## Future work

- Tests for `scoring`, `filters`, and `dedup` against fixture HN responses.
- Additional sources: SEC EDGAR (recent SaaS IPO filings = SOC 2 procurement pressure), Reddit r/devops / r/cybersecurity.
- Per-keyword scoring tuning once we have promote/skip ground truth from Monday triages.
