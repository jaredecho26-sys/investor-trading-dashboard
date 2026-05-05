# Investor Trading Dashboard

Professional dark-mode investor dashboard for daily Schwab account reporting.

## What it does
- Generates a polished HTML dashboard from cached balance history + latest report
- Refreshes automatically from the daily 1:05 PM report job
- Shows equity curve, period returns, drawdown context, and execution summary
- Serves the dashboard locally with a lightweight Python server

## Key files
- `scripts/generate_cached_dashboard.py` — main dashboard generator
- `scripts/generate_daily_report_with_dashboard.py` — daily report + dashboard refresh runner
- `scripts/dashboard_server.py` — local HTTP server
- `scripts/schwab_balance_tracker.py` — cached balance history helper
- `scripts/schwab_token_utils.py` — Schwab token refresh helper

## Notes
This repo intentionally excludes private account data, secrets, and local memory files.
You will need your own Schwab credentials/token files and balance tracker data to run it end-to-end.

## Daily refresh flow
1. Pull fresh Schwab account data
2. Save today's balance snapshot
3. Write the daily trading report
4. Regenerate the dashboard HTML
5. Serve or publish the updated dashboard
