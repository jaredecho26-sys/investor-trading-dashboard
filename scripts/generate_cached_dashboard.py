#!/usr/bin/env python3
"""
Generate a polished investor dashboard from cached balance history and the latest report.
"""

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from string import Template

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
REPORT_DIR = REPO_ROOT / "reports"
DASHBOARD_FILE = REPO_ROOT / "index.html"
LEGACY_DASHBOARD_FILE = REPO_ROOT / "trading-dashboard.html"

POSITIVE = "#22c55e"
NEGATIVE = "#f87171"
NEUTRAL = "#60a5fa"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"


def load_balance_history():
    if not TRACKER_FILE.exists():
        raise FileNotFoundError(f"No balance history found at {TRACKER_FILE}")

    with TRACKER_FILE.open("r") as f:
        raw = json.load(f)

    items = sorted(
        ((datetime.strptime(date_str, "%Y-%m-%d"), float(value)) for date_str, value in raw.items()),
        key=lambda item: item[0],
    )

    if not any(date_obj == INCEPTION_TARGET for date_obj, _ in items):
        items.insert(0, (INCEPTION_TARGET, INCEPTION_BALANCE))

    return items


def find_latest_report():
    if not REPORT_DIR.exists():
        return None, ""

    files = sorted(REPORT_DIR.glob("*-trading-report.md"))
    if not files:
        return None, ""

    latest_file = files[-1]
    return latest_file, latest_file.read_text()


def value_on_or_before(history, target_date):
    for date_obj, value in reversed(history):
        if date_obj <= target_date:
            return value
    return None


def format_currency(value, with_sign=False):
    if value is None:
        return "—"
    return f"{value:+,.2f}" if with_sign else f"{value:,.2f}"


def format_percent(value, with_sign=True):
    if value is None:
        return "—"
    return f"{value:+.2f}%" if with_sign else f"{value:.2f}%"


def change_from_baseline(current_value, baseline_value):
    if baseline_value in (None, 0):
        return None, None
    change_usd = current_value - baseline_value
    change_pct = (change_usd / baseline_value) * 100
    return change_usd, change_pct


def parse_report_metrics(report_text):
    metrics = {}
    patterns = {
        "current_value": r"Current Value:\s*\$([\d,]+\.\d{2})",
        "prior_close": r"Prior Close:\s*\$([\d,]+\.\d{2})",
        "cash_position": r"Cash Position:\s*\$([\d,]+\.\d{2})",
        "filled_7d": r"Last 7 Days:\s*(\d+) filled orders",
        "today_trades": r"Today:\s*(\d+) trades",
        "all_filled": r"Since 10/15/2025:\s*(\d+) trades",
        "generated_time": r"Generated:\s*([^\n]+)",
        "automation_status": r"Automation Status:\s*([^\n]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, report_text)
        if not match:
            metrics[key] = None
            continue

        value = match.group(1).strip()
        if key in {"filled_7d", "today_trades", "all_filled"}:
            metrics[key] = int(value)
        elif key in {"current_value", "prior_close", "cash_position"}:
            metrics[key] = float(value.replace(",", ""))
        else:
            metrics[key] = value

    lines = [line.strip() for line in report_text.splitlines() if line.strip()]
    highlights = []
    for line in lines:
        clean = re.sub(r"^[•💰📈📊⏰✅🔗]+\s*", "", line).strip()
        clean = clean.replace("**", "")
        if clean and clean not in highlights:
            highlights.append(clean)
    metrics["highlights"] = highlights[:8]
    metrics["raw_html"] = html.escape(report_text)
    return metrics


def build_session_rows(history, limit=12):
    rows = []
    recent = history[-limit:]
    previous_value = None
    for date_obj, value in recent:
        if previous_value is None:
            day_change = 0
            day_pct = 0
        else:
            day_change = value - previous_value
            day_pct = (day_change / previous_value * 100) if previous_value else 0
        rows.append(
            {
                "date": date_obj.strftime("%b %d, %Y"),
                "value": f"${format_currency(value)}",
                "change": f"{day_change:+,.2f}",
                "change_pct": f"{day_pct:+.2f}%",
                "tone": "positive" if day_change > 0 else "negative" if day_change < 0 else "neutral",
            }
        )
        previous_value = value
    return rows[::-1]


def generate_dashboard(open_after=False):
    history = load_balance_history()
    latest_report_file, latest_report_text = find_latest_report()
    report_metrics = parse_report_metrics(latest_report_text) if latest_report_text else {
        "highlights": [],
        "raw_html": "No report available yet.",
        "current_value": None,
        "prior_close": None,
        "cash_position": None,
        "filled_7d": None,
        "today_trades": None,
        "all_filled": None,
        "generated_time": None,
        "automation_status": None,
    }

    latest_date, current_value = history[-1]
    previous_date, previous_value = history[-2] if len(history) > 1 else history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = next((value for date_obj, value in history if date_obj == INCEPTION_TARGET), INCEPTION_BALANCE)

    trailing_60 = history[-60:] if len(history) >= 60 else history
    trailing_30 = history[-30:] if len(history) >= 30 else history

    baseline_7 = value_on_or_before(history, latest_date - timedelta(days=7))
    baseline_30 = value_on_or_before(history, latest_date - timedelta(days=30))
    baseline_ytd = value_on_or_before(history, datetime(latest_date.year, 1, 1))

    daily_usd, daily_pct = change_from_baseline(current_value, previous_value)
    seven_usd, seven_pct = change_from_baseline(current_value, baseline_7)
    thirty_usd, thirty_pct = change_from_baseline(current_value, baseline_30)
    ytd_usd, ytd_pct = change_from_baseline(current_value, baseline_ytd)
    inception_usd, inception_pct = change_from_baseline(current_value, inception_value)

    all_time_high_date, all_time_high = max(history, key=lambda item: item[1])
    sixty_high = max(value for _, value in trailing_60)
    sixty_low = min(value for _, value in trailing_60)
    drawdown_pct = ((current_value - all_time_high) / all_time_high * 100) if all_time_high else 0
    drawdown_usd = current_value - all_time_high
    distance_60_high_pct = ((current_value - sixty_high) / sixty_high * 100) if sixty_high else 0

    daily_diffs_30 = []
    for idx in range(1, len(trailing_30)):
        prev_value = trailing_30[idx - 1][1]
        curr_value = trailing_30[idx][1]
        if prev_value:
            daily_diffs_30.append(((curr_value - prev_value) / prev_value) * 100)

    positive_days_30 = sum(1 for diff in daily_diffs_30 if diff > 0)
    flat_days_30 = sum(1 for diff in daily_diffs_30 if diff == 0)
    avg_move_30 = mean(abs(diff) for diff in daily_diffs_30) if daily_diffs_30 else 0

    chart_points = [
        {
            "date": date_obj.strftime("%Y-%m-%d"),
            "label": date_obj.strftime("%b %d"),
            "value": round(value, 2),
        }
        for date_obj, value in history
    ]

    recent_rows = build_session_rows(history)

    report_date_label = latest_report_file.stem.replace("-trading-report", "") if latest_report_file else "—"
    report_date_display = (
        datetime.strptime(report_date_label, "%Y-%m-%d").strftime("%b %d, %Y")
        if report_date_label != "—"
        else "—"
    )

    summary_items = [
        ("All-time high", f"${format_currency(all_time_high)}", all_time_high_date.strftime("%b %d, %Y")),
        ("Current drawdown", format_percent(drawdown_pct), f"${format_currency(drawdown_usd, with_sign=True)} vs peak"),
        ("30D positive sessions", f"{positive_days_30}/{len(daily_diffs_30) or 0}", f"{flat_days_30} flat sessions"),
        ("Avg daily move (30D)", format_percent(avg_move_30), "Absolute daily % move"),
    ]

    stat_cards = [
        {
            "label": "Net liquidating value",
            "value": f"${format_currency(current_value)}",
            "sub": f"As of {latest_date.strftime('%b %d, %Y')}",
            "tone": "neutral",
        },
        {
            "label": "Daily P&L",
            "value": f"${format_currency(daily_usd or 0, with_sign=True)}",
            "sub": format_percent(daily_pct or 0),
            "tone": "positive" if (daily_usd or 0) > 0 else "negative" if (daily_usd or 0) < 0 else "neutral",
        },
        {
            "label": "7-day return",
            "value": format_percent(seven_pct or 0),
            "sub": f"${format_currency(seven_usd or 0, with_sign=True)}",
            "tone": "positive" if (seven_pct or 0) > 0 else "negative" if (seven_pct or 0) < 0 else "neutral",
        },
        {
            "label": "30-day return",
            "value": format_percent(thirty_pct or 0),
            "sub": f"${format_currency(thirty_usd or 0, with_sign=True)}",
            "tone": "positive" if (thirty_pct or 0) > 0 else "negative" if (thirty_pct or 0) < 0 else "neutral",
        },
        {
            "label": "YTD return",
            "value": format_percent(ytd_pct or 0),
            "sub": f"${format_currency(ytd_usd or 0, with_sign=True)}",
            "tone": "positive" if (ytd_pct or 0) > 0 else "negative" if (ytd_pct or 0) < 0 else "neutral",
        },
        {
            "label": "Since inception",
            "value": format_percent(inception_pct),
            "sub": (
                f"${format_currency(inception_usd, with_sign=True)} since {inception_date.strftime('%b %d, %Y')}"
                if inception_value is not None
                else f"Baseline missing for {inception_date.strftime('%b %d, %Y')}"
            ),
            "tone": "positive" if (inception_pct or 0) > 0 else "negative" if (inception_pct or 0) < 0 else "neutral",
        },
    ]

    execution_stats = [
        ("Current value", f"${format_currency(report_metrics.get('current_value') or current_value)}"),
        ("Prior close", f"${format_currency(report_metrics.get('prior_close') or previous_value)}"),
        ("Cash position", f"${format_currency(report_metrics.get('cash_position') or current_value)}"),
        ("Today trades", str(report_metrics.get("today_trades") or "—")),
        ("Filled orders (7D)", str(report_metrics.get("filled_7d") or "—")),
        ("Filled orders (ITD)", str(report_metrics.get("all_filled") or "—")),
        ("60D high / low", f"${format_currency(sixty_high)} / ${format_currency(sixty_low)}"),
        ("Distance from 60D high", format_percent(distance_60_high_pct)),
    ]

    period_returns = [
        {"label": "1D", "value": round(daily_pct or 0, 2), "tone": "positive" if (daily_pct or 0) > 0 else "negative" if (daily_pct or 0) < 0 else "neutral"},
        {"label": "7D", "value": round(seven_pct or 0, 2), "tone": "positive" if (seven_pct or 0) > 0 else "negative" if (seven_pct or 0) < 0 else "neutral"},
        {"label": "30D", "value": round(thirty_pct or 0, 2), "tone": "positive" if (thirty_pct or 0) > 0 else "negative" if (thirty_pct or 0) < 0 else "neutral"},
        {"label": "YTD", "value": round(ytd_pct or 0, 2), "tone": "positive" if (ytd_pct or 0) > 0 else "negative" if (ytd_pct or 0) < 0 else "neutral"},
        {"label": "ITD", "value": round(inception_pct or 0, 2), "tone": "positive" if (inception_pct or 0) > 0 else "negative" if (inception_pct or 0) < 0 else "neutral"},
    ]

    html_template = Template(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Investor Trading Dashboard — $report_title_date</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #081120;
      --bg-accent: #0b1730;
      --panel: rgba(15, 23, 42, 0.88);
      --panel-strong: #0f172a;
      --panel-soft: rgba(30, 41, 59, 0.45);
      --border: rgba(148, 163, 184, 0.16);
      --text: #e5e7eb;
      --muted: #a8b4c8;
      --blue: #60a5fa;
      --blue-strong: #3b82f6;
      --green: #22c55e;
      --red: #f87171;
      --amber: #fbbf24;
      --shadow: 0 22px 50px rgba(2, 6, 23, 0.45);
      --radius: 20px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(34, 197, 94, 0.10), transparent 24%),
        linear-gradient(180deg, #081120 0%, #030712 100%);
      color: var(--text);
      min-height: 100vh;
      padding: 32px;
    }

    .shell {
      max-width: 1480px;
      margin: 0 auto;
      display: grid;
      gap: 24px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(20px);
    }

    .hero {
      overflow: hidden;
      position: relative;
      padding: 28px;
    }

    .hero::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(96, 165, 250, 0.16), rgba(15, 23, 42, 0.02) 44%, rgba(34, 197, 94, 0.08));
      pointer-events: none;
    }

    .hero-grid {
      position: relative;
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 24px;
      align-items: stretch;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(96, 165, 250, 0.24);
      background: rgba(96, 165, 250, 0.08);
      color: #bfdbfe;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 18px;
    }

    .hero h1 {
      font-size: clamp(34px, 4vw, 54px);
      line-height: 1.02;
      letter-spacing: -0.04em;
      margin-bottom: 14px;
      max-width: 12ch;
    }

    .hero-copy {
      color: var(--muted);
      font-size: 15px;
      line-height: 1.7;
      max-width: 60ch;
      margin-bottom: 26px;
    }

    .hero-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 18px;
      align-items: flex-end;
    }

    .equity-block {
      min-width: 260px;
    }

    .kicker {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 10px;
    }

    .equity-value {
      font-size: clamp(40px, 5vw, 64px);
      line-height: 0.95;
      letter-spacing: -0.05em;
      font-weight: 700;
    }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
      color: var(--muted);
      font-size: 13px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border);
      color: var(--text);
      min-width: 150px;
    }

    .badge strong {
      display: block;
      font-size: 13px;
      margin-bottom: 2px;
    }

    .badge span {
      color: var(--muted);
      font-size: 12px;
    }

    .summary-stack {
      display: grid;
      gap: 14px;
      align-content: start;
    }

    .summary-card {
      background: rgba(15, 23, 42, 0.68);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
    }

    .summary-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }

    .summary-value {
      font-size: 28px;
      letter-spacing: -0.03em;
      margin-bottom: 6px;
    }

    .summary-note {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }

    .cards-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 16px;
    }

    .stat-card {
      padding: 20px;
      min-height: 148px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(15, 23, 42, 0.74));
    }

    .stat-card .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .stat-card .value {
      font-size: 30px;
      line-height: 1;
      letter-spacing: -0.04em;
      margin: 16px 0 10px;
    }

    .stat-card .sub {
      color: var(--muted);
      font-size: 13px;
    }

    .positive { color: var(--green); }
    .negative { color: var(--red); }
    .neutral { color: var(--blue); }

    .content-grid {
      display: grid;
      grid-template-columns: 1.7fr 1fr;
      gap: 24px;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 22px;
    }

    .title-group h2 {
      font-size: 22px;
      letter-spacing: -0.03em;
      margin-bottom: 6px;
    }

    .title-group p {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }

    .range-toggle {
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.72);
      border: 1px solid var(--border);
    }

    .range-toggle button {
      border: 0;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      cursor: pointer;
      color: var(--muted);
      background: transparent;
      transition: 0.18s ease;
    }

    .range-toggle button.active {
      background: rgba(96, 165, 250, 0.14);
      color: #dbeafe;
      box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.22);
    }

    .chart-panel,
    .sidebar-card,
    .briefing-card,
    .table-card {
      padding: 24px;
    }

    .chart-wrap {
      height: 360px;
    }

    .sidebar-stack {
      display: grid;
      gap: 24px;
    }

    .mini-chart-wrap {
      height: 220px;
      margin-bottom: 18px;
    }

    .metric-list {
      display: grid;
      gap: 12px;
    }

    .metric-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      padding: 12px 0;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    }

    .metric-row:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }

    .metric-row .row-label {
      color: var(--muted);
      font-size: 13px;
    }

    .metric-row .row-value {
      font-size: 14px;
      font-weight: 600;
      text-align: right;
    }

    .lower-grid {
      display: grid;
      grid-template-columns: 1.08fr 0.92fr;
      gap: 24px;
    }

    .briefing-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }

    .briefing-tile {
      padding: 16px;
      border-radius: 16px;
      background: rgba(15, 23, 42, 0.58);
      border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .briefing-tile .tile-label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .briefing-tile .tile-value {
      font-size: 20px;
      letter-spacing: -0.03em;
    }

    .highlights {
      display: grid;
      gap: 10px;
      margin: 18px 0;
    }

    .highlight-row {
      display: block;
      color: var(--text);
      font-size: 14px;
      line-height: 1.6;
      padding: 14px 16px;
      border-radius: 14px;
      background: rgba(15, 23, 42, 0.58);
      border: 1px solid rgba(148, 163, 184, 0.1);
      border-left: 3px solid rgba(96, 165, 250, 0.7);
    }

    details {
      border-top: 1px solid rgba(148, 163, 184, 0.12);
      padding-top: 16px;
      margin-top: 18px;
    }

    summary {
      cursor: pointer;
      color: #dbeafe;
      font-weight: 600;
      list-style: none;
    }

    summary::-webkit-details-marker {
      display: none;
    }

    .raw-report {
      margin-top: 14px;
      color: var(--muted);
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      line-height: 1.75;
      max-height: 320px;
      overflow: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th,
    td {
      text-align: left;
      padding: 14px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      font-size: 14px;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 600;
    }

    tbody tr:hover {
      background: rgba(30, 41, 59, 0.28);
    }

    .table-card footer {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      padding-top: 16px;
      color: var(--muted);
      font-size: 12px;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.10);
      border: 1px solid rgba(34, 197, 94, 0.2);
      color: #bbf7d0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    @media (max-width: 1280px) {
      .cards-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @media (max-width: 1080px) {
      body { padding: 20px; }
      .hero-grid,
      .content-grid,
      .lower-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 820px) {
      body { padding: 16px; }
      .shell { gap: 16px; }
      .panel { border-radius: 16px; }
      .hero { padding: 20px; }
      .hero h1 { font-size: clamp(28px, 5vw, 40px); }
      .chart-panel,
      .sidebar-card,
      .briefing-card,
      .table-card { padding: 16px; }
      .cards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      .stat-card { padding: 16px; min-height: 140px; }
      .stat-card .value { font-size: 24px; margin: 12px 0 8px; }
      .stat-card .label { font-size: 11px; }
      .stat-card .sub { font-size: 12px; }
      .hero-metrics { gap: 12px; }
      .badge { min-width: 140px; padding: 8px 12px; }
      .badge strong { font-size: 12px; }
      .badge span { font-size: 11px; }
      .equity-block { min-width: 200px; }
      .equity-value { font-size: clamp(32px, 4vw, 48px); }
      .summary-card { padding: 14px; }
      .summary-value { font-size: 24px; }
      .chart-wrap { height: 280px; }
      .metric-row { padding: 10px 0; font-size: 13px; }
      .briefing-grid { gap: 12px; }
      .briefing-tile { padding: 14px; }
      .briefing-tile .tile-value { font-size: 18px; }
    }

    @media (max-width: 720px) {
      body { padding: 12px; }
      .shell { gap: 14px; }
      .hero { padding: 16px; }
      .hero h1 { font-size: clamp(24px, 4vw, 32px); margin-bottom: 10px; }
      .hero-copy { font-size: 14px; margin-bottom: 18px; }
      .cards-grid,
      .briefing-grid {
        grid-template-columns: 1fr;
        gap: 10px;
      }

      .card-header {
        flex-direction: column;
        align-items: stretch;
        margin-bottom: 16px;
      }

      .range-toggle {
        width: 100%;
        justify-content: space-between;
      }

      th:nth-child(2), td:nth-child(2) {
        display: none;
      }

      .stat-card { padding: 14px; min-height: 130px; }
      .stat-card .value { font-size: 22px; margin: 10px 0 6px; }
      .stat-card .label { font-size: 10px; }
      .stat-card .sub { font-size: 11px; }
      .kicker { font-size: 11px; margin-bottom: 8px; }
      .hero-metrics { flex-direction: column; gap: 10px; }
      .equity-block { min-width: unset; }
      .badge { width: 100%; min-width: unset; }
      .summary-card { padding: 12px; }
      .summary-value { font-size: 20px; }
      .summary-label { font-size: 11px; margin-bottom: 6px; }
      .summary-note { font-size: 12px; }
      .chart-wrap { height: 240px; }
      .mini-chart-wrap { height: 180px; margin-bottom: 14px; }
      .metric-row { padding: 8px 0; font-size: 12px; gap: 12px; }
      .metric-row .row-label { flex: 1; }
      .metric-row .row-value { text-align: right; }
      .briefing-tile { padding: 12px; }
      .briefing-tile .tile-value { font-size: 16px; }
      .briefing-tile .tile-label { font-size: 11px; margin-bottom: 6px; }
      .eyebrow { font-size: 11px; padding: 6px 10px; margin-bottom: 12px; }
      .hero-meta { font-size: 12px; }
      .title-group h2 { font-size: 18px; margin-bottom: 4px; }
      .title-group p { font-size: 13px; }
      table { font-size: 12px; }
      th { padding: 10px 8px; }
      td { padding: 10px 8px; }
    }

    @media (max-width: 480px) {
      body { padding: 8px; }
      .shell { gap: 10px; }
      .panel { border-radius: 12px; }
      .hero { padding: 12px; }
      .hero h1 { font-size: 20px; margin-bottom: 8px; line-height: 1.1; }
      .hero-copy { font-size: 13px; margin-bottom: 12px; line-height: 1.5; }
      .chart-panel,
      .sidebar-card,
      .briefing-card,
      .table-card { padding: 12px; }
      .cards-grid { gap: 8px; }
      .stat-card { padding: 12px; min-height: 120px; }
      .stat-card .value { font-size: 18px; margin: 8px 0 4px; }
      .stat-card .label { font-size: 9px; }
      .stat-card .sub { font-size: 10px; }
      .kicker { font-size: 10px; }
      .equity-value { font-size: 28px; }
      .badge { padding: 6px 10px; }
      .badge strong { font-size: 11px; }
      .badge span { font-size: 10px; }
      .summary-card { padding: 10px; }
      .summary-value { font-size: 18px; }
      .summary-label { font-size: 10px; }
      .chart-wrap { height: 200px; }
      .mini-chart-wrap { height: 150px; margin-bottom: 10px; }
      .metric-row { padding: 6px 0; font-size: 11px; }
      .briefing-grid { gap: 8px; }
      .briefing-tile { padding: 10px; }
      .briefing-tile .tile-value { font-size: 14px; }
      .briefing-tile .tile-label { font-size: 10px; }
      .eyebrow { font-size: 10px; padding: 5px 8px; }
      .hero-meta { font-size: 11px; flex-direction: column; gap: 4px; }
      .hero-meta span { display: none; }
      .hero-meta span:first-child { display: inline; }
      .title-group h2 { font-size: 16px; }
      .title-group p { font-size: 12px; }
      table { font-size: 11px; }
      th, td { padding: 8px 6px; }
      .range-toggle button { padding: 6px 10px; font-size: 11px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="panel hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Investor view • Institutional layout • Daily refresh</div>
          <h1>Trading performance dashboard.</h1>
          <p class="hero-copy">A cleaner, more professional surface for equity, returns, risk context, and execution activity — built to feel closer to TradeZella-grade polish without turning into a toy dashboard.</p>
          <div class="hero-metrics">
            <div class="equity-block">
              <div class="kicker">Net liquidating value</div>
              <div class="equity-value">$$$equity_value</div>
              <div class="hero-meta">
                <span>As of $latest_date_display</span>
                <span>•</span>
                <span>Latest report: $report_date_display</span>
                <span>•</span>
                <span id="current-time"></span>
              </div>
            </div>
            <div class="badge">
              <div>
                <strong class="$hero_pnl_tone">$hero_pnl_value</strong>
                <span>Daily P&amp;L</span>
              </div>
            </div>
            <div class="badge">
              <div>
                <strong class="$hero_drawdown_tone">$hero_drawdown_value</strong>
                <span>Current drawdown vs peak</span>
              </div>
            </div>
          </div>
        </div>
        <div class="summary-stack">
          $summary_cards_html
        </div>
      </div>
    </section>

    <section class="cards-grid">
      $stat_cards_html
    </section>

    <section class="content-grid">
      <div class="panel chart-panel">
        <div class="card-header">
          <div class="title-group">
            <h2>Equity curve</h2>
            <p>Professional top-level read on the account curve with quick time-range filters.</p>
          </div>
          <div class="range-toggle" aria-label="Chart range toggles">
            <button class="active" data-range="30">30D</button>
            <button data-range="60">60D</button>
            <button data-range="120">120D</button>
            <button data-range="all">All</button>
          </div>
        </div>
        <div class="chart-wrap">
          <canvas id="equityChart"></canvas>
        </div>
      </div>

      <div class="sidebar-stack">
        <aside class="panel sidebar-card">
          <div class="card-header">
            <div class="title-group">
              <h2>Return stack</h2>
              <p>Single-pattern period comparison. No chart zoo nonsense.</p>
            </div>
          </div>
          <div class="mini-chart-wrap">
            <canvas id="returnsChart"></canvas>
          </div>
          <div class="metric-list">
            $execution_rows_html
          </div>
        </aside>
      </div>
    </section>

    <section class="lower-grid">
      <div class="panel briefing-card">
        <div class="card-header">
          <div class="title-group">
            <h2>Execution summary</h2>
            <p>Operational context pulled from the latest daily report and the cached balance history.</p>
          </div>
          <div class="status-pill">$automation_status</div>
        </div>
        <div class="briefing-grid">
          $briefing_tiles_html
        </div>
        <div class="highlights">
          $highlights_html
        </div>
        <details>
          <summary>View raw daily report</summary>
          <div class="raw-report">$raw_report_html</div>
        </details>
      </div>

      <div class="panel briefing-card">
        <div class="card-header">
          <div class="title-group">
            <h2>Risk context</h2>
            <p>The handful of numbers that actually matter when someone asks how the account is behaving.</p>
          </div>
        </div>
        <div class="metric-list">
          $risk_rows_html
        </div>
      </div>
    </section>

    <section class="panel table-card">
      <div class="card-header">
        <div class="title-group">
          <h2>Recent session ledger</h2>
          <p>Clean daily tape for the last $session_row_count entries.</p>
        </div>
      </div>
      <div style="overflow:auto;">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Account Value</th>
              <th>Day Change</th>
              <th>Return</th>
            </tr>
          </thead>
          <tbody>
            $session_rows_html
          </tbody>
        </table>
      </div>
      <footer>
        <span>Source: cached balance history + latest trading report</span>
        <span>Dashboard refreshes when the daily report job writes new data</span>
      </footer>
    </section>
  </div>

  <script>
    const chartPoints = $chart_points_json;
    const returnsData = $period_returns_json;

    function toneColor(tone) {
      if (tone === 'positive') return '$positive_color';
      if (tone === 'negative') return '$negative_color';
      return '$neutral_color';
    }

    function updateClock() {
      const now = new Date();
      document.getElementById('current-time').textContent = now.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
      });
    }
    updateClock();
    setInterval(updateClock, 60000);

    const equityCtx = document.getElementById('equityChart').getContext('2d');
    const gradient = equityCtx.createLinearGradient(0, 0, 0, 420);
    gradient.addColorStop(0, 'rgba(96, 165, 250, 0.34)');
    gradient.addColorStop(1, 'rgba(96, 165, 250, 0.02)');

    function slicePoints(range) {
      if (range === 'all') return chartPoints;
      return chartPoints.slice(-Number(range));
    }

    const equityChart = new Chart(equityCtx, {
      type: 'line',
      data: {
        labels: slicePoints('30').map(point => point.label),
        datasets: [{
          label: 'Account value',
          data: slicePoints('30').map(point => point.value),
          borderColor: '$neutral_color',
          borderWidth: 2,
          tension: 0.28,
          pointRadius: 0,
          fill: true,
          backgroundColor: gradient
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(148, 163, 184, 0.16)',
            borderWidth: 1,
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            padding: 12,
            displayColors: false,
            callbacks: {
              label: (context) => '$$' + context.parsed.y.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(148, 163, 184, 0.06)' },
            ticks: { color: '#94a3b8', maxTicksLimit: 8 }
          },
          y: {
            grid: { color: 'rgba(148, 163, 184, 0.08)' },
            ticks: {
              color: '#94a3b8',
              callback: (value) => '$$' + Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })
            }
          }
        }
      }
    });

    document.querySelectorAll('[data-range]').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('[data-range]').forEach((btn) => btn.classList.remove('active'));
        button.classList.add('active');
        const subset = slicePoints(button.dataset.range);
        equityChart.data.labels = subset.map(point => point.label);
        equityChart.data.datasets[0].data = subset.map(point => point.value);
        equityChart.update();
      });
    });

    const valueLabelPlugin = {
      id: 'valueLabelPlugin',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.font = '600 11px Inter, sans-serif';
        ctx.textBaseline = 'middle';

        meta.data.forEach((bar, index) => {
          const value = chart.data.datasets[0].data[index];
          const label = value.toFixed(2) + '%';
          ctx.fillStyle = value >= 0 ? '#d1fae5' : '#fecaca';
          ctx.textAlign = value >= 0 ? 'left' : 'right';
          ctx.fillText(label, value >= 0 ? bar.x + 8 : bar.x - 8, bar.y);
        });

        ctx.restore();
      }
    };

    const returnsCtx = document.getElementById('returnsChart').getContext('2d');
    new Chart(returnsCtx, {
      type: 'bar',
      data: {
        labels: returnsData.map(item => item.label),
        datasets: [{
          data: returnsData.map(item => item.value),
          backgroundColor: returnsData.map(item => toneColor(item.tone)),
          borderRadius: 10,
          borderSkipped: false,
          barThickness: 18,
          maxBarThickness: 18
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        layout: {
          padding: { right: 44, left: 8 }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(148, 163, 184, 0.16)',
            borderWidth: 1,
            displayColors: false,
            callbacks: {
              label: (context) => context.parsed.x.toFixed(2) + '%'
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(148, 163, 184, 0.08)' },
            ticks: {
              color: '#a8b4c8',
              callback: (value) => Number(value).toFixed(0) + '%'
            }
          },
          y: {
            grid: { display: false },
            ticks: { color: '#dbe3f0' }
          }
        }
      },
      plugins: [valueLabelPlugin]
    });
  </script>
</body>
</html>
"""
    )

    summary_cards_html = "".join(
        f'''
        <div class="summary-card">
          <div class="summary-label">{html.escape(label)}</div>
          <div class="summary-value {'positive' if '-' not in value and value != '—' and value != '0/0' else 'negative' if value.startswith('-') else ''}">{html.escape(value)}</div>
          <div class="summary-note">{html.escape(note)}</div>
        </div>
        '''
        for label, value, note in summary_items
    )

    stat_cards_html = "".join(
        f'''
        <article class="panel stat-card">
          <div class="label">{html.escape(card['label'])}</div>
          <div>
            <div class="value {card['tone']}">{html.escape(card['value'])}</div>
            <div class="sub">{html.escape(card['sub'])}</div>
          </div>
        </article>
        '''
        for card in stat_cards
    )

    execution_rows_html = "".join(
        f'''
        <div class="metric-row">
          <div class="row-label">{html.escape(label)}</div>
          <div class="row-value">{html.escape(value)}</div>
        </div>
        '''
        for label, value in execution_stats
    )

    briefing_tiles = [
        ("Report generated", report_metrics.get("generated_time") or "—"),
        ("Today trades", str(report_metrics.get("today_trades") or "—")),
        ("7D filled orders", str(report_metrics.get("filled_7d") or "—")),
        ("Since inception trades", str(report_metrics.get("all_filled") or "—")),
    ]
    briefing_tiles_html = "".join(
        f'''
        <div class="briefing-tile">
          <div class="tile-label">{html.escape(label)}</div>
          <div class="tile-value">{html.escape(value)}</div>
        </div>
        '''
        for label, value in briefing_tiles
    )

    highlights = report_metrics.get("highlights") or ["No report highlights available yet."]
    highlights_html = "".join(
        f'''
        <div class="highlight-row">{html.escape(line)}</div>
        '''
        for line in highlights
    )

    risk_rows = [
        ("Inception date", inception_date.strftime("%b %d, %Y")),
        ("Inception balance", f"${format_currency(inception_value)}" if inception_value is not None else "Missing in tracker"),
        ("All-time high date", all_time_high_date.strftime("%b %d, %Y")),
        ("Drawdown from peak", f"{format_percent(drawdown_pct)} • ${format_currency(drawdown_usd, with_sign=True)}"),
        ("30D positive sessions", f"{positive_days_30}/{len(daily_diffs_30) or 0}"),
        ("30D average absolute move", format_percent(avg_move_30)),
        ("Latest report file", report_date_display),
        ("Latest balance date", latest_date.strftime("%b %d, %Y")),
    ]
    risk_rows_html = "".join(
        f'''
        <div class="metric-row">
          <div class="row-label">{html.escape(label)}</div>
          <div class="row-value">{html.escape(value)}</div>
        </div>
        '''
        for label, value in risk_rows
    )

    session_rows_html = "".join(
        f'''
        <tr>
          <td>{html.escape(row['date'])}</td>
          <td>{html.escape(row['value'])}</td>
          <td class="{row['tone']}">{html.escape(row['change'])}</td>
          <td class="{row['tone']}">{html.escape(row['change_pct'])}</td>
        </tr>
        '''
        for row in recent_rows
    )

    rendered = html_template.substitute(
        report_title_date=latest_date.strftime("%B %d, %Y"),
        equity_value=format_currency(current_value),
        latest_date_display=latest_date.strftime("%b %d, %Y"),
        report_date_display=report_date_display,
        hero_pnl_tone="positive" if (daily_usd or 0) > 0 else "negative" if (daily_usd or 0) < 0 else "neutral",
        hero_pnl_value=f"${format_currency(daily_usd or 0, with_sign=True)} · {format_percent(daily_pct or 0)}",
        hero_drawdown_tone="positive" if drawdown_pct >= 0 else "negative",
        hero_drawdown_value=format_percent(drawdown_pct),
        summary_cards_html=summary_cards_html,
        stat_cards_html=stat_cards_html,
        execution_rows_html=execution_rows_html,
        briefing_tiles_html=briefing_tiles_html,
        highlights_html=highlights_html,
        raw_report_html=report_metrics.get("raw_html", "No report available yet."),
        automation_status=report_metrics.get("automation_status") or "Working",
        risk_rows_html=risk_rows_html,
        session_row_count=str(len(recent_rows)),
        session_rows_html=session_rows_html,
        chart_points_json=json.dumps(chart_points),
        period_returns_json=json.dumps(period_returns),
        positive_color=POSITIVE,
        negative_color=NEGATIVE,
        neutral_color=NEUTRAL,
    )

    DASHBOARD_FILE.write_text(rendered)
    LEGACY_DASHBOARD_FILE.write_text(rendered)
    print(f"✓ Dashboard generated: {DASHBOARD_FILE}")

    if open_after:
        subprocess.run(["open", str(DASHBOARD_FILE)], check=False)

    return True


if __name__ == "__main__":
    should_open = "--open" in sys.argv
    try:
        success = generate_dashboard(open_after=should_open)
        sys.exit(0 if success else 1)
    except Exception as exc:
        print(f"❌ Error generating dashboard: {exc}")
        sys.exit(1)
