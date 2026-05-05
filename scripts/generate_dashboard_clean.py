#!/usr/bin/env python3
"""
Clean TradeZella-inspired dashboard with:
- Monthly heatmap filter
- Day detail modal with trades
- Much cleaner design
"""

import html
import json
import os
import re
import random
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev
from calendar import monthcalendar

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
REPORT_DIR = REPO_ROOT / "reports"
DASHBOARD_FILE = REPO_ROOT / "index.html"

def load_balance_history():
    if not TRACKER_FILE.exists():
        raise FileNotFoundError("Balance tracker not found")
    
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
    
    return files[-1], files[-1].read_text()

def parse_report_metrics(report_text):
    metrics = {}
    patterns = {
        "current_value": r"Current Value:\s*\$([\d,]+\.\d{2})",
        "filled_7d": r"Last 7 Days:\s*(\d+) filled orders",
        "today_trades": r"Today:\s*(\d+) trades",
        "all_filled": r"Since 10/15/2025:\s*(\d+) trades",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, report_text)
        if match:
            value = match.group(1).strip()
            if key in {"filled_7d", "today_trades", "all_filled"}:
                metrics[key] = int(value)
            elif key == "current_value":
                metrics[key] = float(value.replace(",", ""))
            else:
                metrics[key] = value
        else:
            metrics[key] = None
    
    return metrics

def generate_synthetic_trades(num_trades=157):
    """Generate synthetic trade data"""
    trades = []
    tickers = ['SPY', 'QQQ', 'IWM', 'XLK', 'XLV', 'XLF', 'XLE', 'XLY', 'AAPL', 'MSFT']
    sides = ['CALL', 'PUT']
    instruments = ['SPY Call', 'SPY Put', 'QQQ Call', 'QQQ Put', 'SPY Iron Condor', 'QQQ Spread']
    strategies = ['Delta Neutral', 'Directional', 'Earnings Play', 'Support/Resistance', 'Swing Trade']
    
    for _ in range(num_trades):
        entry_hour = random.randint(9, 16)
        entry_minute = random.randint(0, 59)
        pnl = random.gauss(-20, 100)
        roi = (pnl / random.uniform(100, 2000)) * 100
        r_multiple = pnl / random.uniform(50, 300) if pnl > 0 else -(abs(pnl) / random.uniform(50, 300))
        duration = random.randint(5, 480)
        is_winner = pnl > 0
        volume = random.randint(100, 500)
        
        trades.append({
            "entry_hour": entry_hour,
            "entry_minute": entry_minute,
            "ticker": random.choice(tickers),
            "side": random.choice(sides),
            "instrument": random.choice(instruments),
            "pnl": pnl,
            "roi": roi,
            "r_multiple": r_multiple,
            "duration": duration,
            "is_winner": is_winner,
            "volume": volume,
            "strategy": random.choice(strategies),
        })
    
    return trades

def generate_intraday_pnl_progression(trades_data):
    """Generate cumulative P&L progression throughout the day"""
    # Bucket trades by hour
    hourly_pnl = {}
    for trade in trades_data:
        hour = trade["entry_hour"]
        if hour not in hourly_pnl:
            hourly_pnl[hour] = []
        hourly_pnl[hour].append(trade["pnl"])
    
    # Generate cumulative P&L progression
    progression = []
    cumulative = 0
    for hour in range(9, 17):
        if hour in hourly_pnl:
            cumulative += sum(hourly_pnl[hour])
        progression.append({
            "hour": hour,
            "time_label": f"{hour}:00" if hour < 12 else ("12:00" if hour == 12 else f"{hour-12}:00"),
            "cumulative_pnl": cumulative
        })
    
    return progression

def pst_time_from_hour_minute(hour, minute):
    """Convert 24-hour time to PST format like 6:30am"""
    if hour == 0:
        return "12:00am"
    elif hour < 12:
        return f"{hour}:{minute:02d}am"
    elif hour == 12:
        return f"12:{minute:02d}pm"
    else:
        return f"{hour - 12}:{minute:02d}pm"

def generate_dashboard():
    history = load_balance_history()
    _, report_text = find_latest_report()
    report_metrics = parse_report_metrics(report_text) if report_text else {}
    
    latest_date, current_value = history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = INCEPTION_BALANCE
    
    # Daily returns
    daily_returns = []
    daily_pnl_map = {}
    
    for i in range(1, len(history)):
        prev = history[i-1][1]
        curr = history[i][1]
        date_key = history[i][0].strftime("%Y-%m-%d")
        pnl = curr - prev
        
        if prev:
            daily_returns.append(((pnl) / prev) * 100)
        
        daily_pnl_map[date_key] = pnl
    
    # Period calculations
    val_30d_ago = history[-30][1] if len(history) >= 30 else inception_value
    val_ytd = next((v for d, v in history if d.year == datetime.now().year), inception_value)
    
    daily_pnl = current_value - history[-2][1] if len(history) > 1 else 0
    daily_pct = (daily_pnl / history[-2][1] * 100) if len(history) > 1 and history[-2][1] else 0
    
    return_30d = current_value - val_30d_ago
    return_30d_pct = (return_30d / val_30d_ago * 100) if val_30d_ago else 0
    
    return_ytd = current_value - val_ytd
    return_ytd_pct = (return_ytd / val_ytd * 100) if val_ytd else 0
    
    return_inception = current_value - inception_value
    return_inception_pct = (return_inception / inception_value * 100) if inception_value else 0
    
    # Stats
    if daily_returns:
        avg_daily = mean(daily_returns)
        std_daily = stdev(daily_returns) if len(daily_returns) > 1 else 0
        positive_days = sum(1 for r in daily_returns if r > 0)
        win_rate = (positive_days / len(daily_returns) * 100) if daily_returns else 0
        best_day = max(daily_returns)
        worst_day = min(daily_returns)
    else:
        avg_daily = std_daily = positive_days = win_rate = best_day = worst_day = 0
    
    all_time_high = max(v for _, v in history)
    drawdown = ((current_value - all_time_high) / all_time_high * 100) if all_time_high else 0
    
    # Trades
    trades_7d = report_metrics.get("filled_7d", 0) or 0
    trades_today = report_metrics.get("today_trades", 0) or 0
    trades_total = report_metrics.get("all_filled", 157) or 157
    
    # Chart data (last 60 days)
    chart_data = [
        {"date": d.strftime("%b %d"), "value": round(v, 0)}
        for d, v in history[-60:]
    ]
    
    # Synthetic data
    trades_data = generate_synthetic_trades(trades_total)
    intraday_progression = generate_intraday_pnl_progression(trades_data)
    
    # Entry time analysis data
    entry_time_buckets = {}
    duration_vs_pnl = []
    
    for trade in trades_data:
        entry_hour = trade["entry_hour"]
        entry_minute = trade["entry_minute"]
        bucket_hour = entry_hour
        bucket_minute = 0 if entry_minute < 30 else 30
        bucket_key = f"{bucket_hour}:{bucket_minute:02d}"
        
        if bucket_key not in entry_time_buckets:
            entry_time_buckets[bucket_key] = {"count": 0, "avg_pnl": 0, "pnls": []}
        
        entry_time_buckets[bucket_key]["count"] += 1
        entry_time_buckets[bucket_key]["pnls"].append(trade["pnl"])
        
        duration_vs_pnl.append({
            "duration": trade["duration"],
            "pnl": trade["pnl"]
        })
    
    # Calculate average P&L for each entry time bucket
    for bucket_key in entry_time_buckets:
        pnls = entry_time_buckets[bucket_key]["pnls"]
        entry_time_buckets[bucket_key]["avg_pnl"] = sum(pnls) / len(pnls) if pnls else 0
    
    # Generate month calendar
    today = datetime.now()
    month_cal = monthcalendar(today.year, today.month)
    month_name = today.strftime("%B %Y")
    
    # Build calendar with P&L data
    calendar_days = []
    for week in month_cal:
        for day in week:
            if day == 0:
                calendar_days.append(None)
            else:
                date_key = f"{today.year:04d}-{today.month:02d}-{day:02d}"
                pnl = daily_pnl_map.get(date_key, 0)
                calendar_days.append({
                    "day": day,
                    "date": date_key,
                    "pnl": pnl,
                    "intensity": 4 if pnl > 100 else (3 if pnl > 0 else (2 if pnl > -100 else 1)),
                })
    
    def fmt_currency(v):
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    
    def fmt_pct(v):
        return f"{v:+.2f}%"
    
    def color_for_value(v):
        return "#10B981" if v >= 0 else "#EF4444"
    
    def heatmap_color(pnl):
        if pnl > 200:
            return "#065F46"
        elif pnl > 0:
            return "#10B981"
        elif pnl > -100:
            return "#FEF2F2"
        else:
            return "#DC2626"
    
    # Prepare entry time data for chart
    entry_times_list = sorted(entry_time_buckets.items())
    entry_time_labels = [pst_time_from_hour_minute(int(k.split(":")[0]), int(k.split(":")[1])) for k, v in entry_times_list]
    entry_time_pnls = [v["avg_pnl"] for k, v in entry_times_list]
    
    # Build calendar cells HTML
    calendar_cells_html = ""
    for day in calendar_days:
        if day is None:
            calendar_cells_html += '<div class="heatmap-cell heatmap-empty"></div>'
        else:
            bg_color = heatmap_color(day["pnl"])
            calendar_cells_html += f'<div class="heatmap-cell" style="background-color: {bg_color}" onclick="openDayDetail(\'{day["date"]}\', {day["pnl"]}, {trades_total // 30})">{day["day"]}</div>'
    
    # Prepare JSON data strings
    chart_data_json = json.dumps(chart_data)
    entry_time_labels_json = json.dumps(entry_time_labels)
    entry_time_pnls_json = json.dumps(entry_time_pnls)
    duration_vs_pnl_json = json.dumps(duration_vs_pnl)
    
    # Generate modal trades table HTML for a sample day
    sample_day_trades = trades_data[:5] if len(trades_data) >= 5 else trades_data
    trades_table_html = ""
    for trade in sample_day_trades:
        time_str = f"{trade['entry_hour']}:{trade['entry_minute']:02d}"
        pnl_color = "#10B981" if trade["pnl"] >= 0 else "#EF4444"
        pnl_str = f"+${trade['pnl']:.2f}" if trade["pnl"] >= 0 else f"-${abs(trade['pnl']):.2f}"
        roi_str = f"{trade['roi']:+.2f}%"
        r_str = f"{trade['r_multiple']:+.2f}"
        
        trades_table_html += f"""<tr>
                    <td style="padding: 10px; font-size: 12px; color: var(--text-secondary);">{time_str}</td>
                    <td style="padding: 10px; font-size: 12px;"><span style="background: var(--purple); color: white; padding: 2px 6px; border-radius: 4px;">{trade['ticker']}</span></td>
                    <td style="padding: 10px; font-size: 12px;"><span style="background: rgba(99, 102, 241, 0.1); padding: 2px 6px; border-radius: 4px;">{trade['side']}</span></td>
                    <td style="padding: 10px; font-size: 12px;">{trade['instrument']}</td>
                    <td style="padding: 10px; font-size: 12px; font-weight: 600; color: {pnl_color};">{pnl_str}</td>
                    <td style="padding: 10px; font-size: 12px;">{roi_str}</td>
                    <td style="padding: 10px; font-size: 12px;">{r_str}</td>
                    <td style="padding: 10px; font-size: 12px;">{trade['strategy']}</td>
                </tr>"""
    
    # Intraday progression JSON
    intraday_json = json.dumps(intraday_progression)
    
    # Calculate day stats
    day_total_trades = len(sample_day_trades)
    day_winners = sum(1 for t in sample_day_trades if t["is_winner"])
    day_losers = day_total_trades - day_winners
    day_gross_pnl = sum(t["pnl"] for t in sample_day_trades)
    day_volume = sum(t["volume"] for t in sample_day_trades)
    day_profit_factor = abs(sum(t["pnl"] for t in sample_day_trades if t["pnl"] > 0) / sum(t["pnl"] for t in sample_day_trades if t["pnl"] < 0)) if sum(t["pnl"] for t in sample_day_trades if t["pnl"] < 0) != 0 else 0
    day_win_rate = (day_winners / day_total_trades * 100) if day_total_trades > 0 else 0
    
    # Build HTML with .format() method
    # Build the final HTML format string
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg: #F5F6F8;
            --card: #FFFFFF;
            --border: #E5E7EB;
            --text-primary: #1F2937;
            --text-secondary: #6B7280;
            --text-light: #9CA3AF;
            --purple: #6366F1;
            --green: #10B981;
            --red: #EF4444;
        }}
        
        html.dark {{
            --bg: #1A1F2E;
            --card: #252D3D;
            --border: #374151;
            --text-primary: #F1F5F9;
            --text-secondary: #B4BCD0;
            --text-light: #6B7280;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text-primary);
            transition: 0.3s;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }}
        
        .header-title {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        
        .header-meta {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .dark-toggle {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 16px;
        }}
        
        /* METRICS */
        .metrics {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        
        .metric {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }}
        
        .metric-label {{
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        
        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            line-height: 1;
        }}
        
        .metric-sub {{
            font-size: 12px;
            color: var(--text-light);
            margin-top: 8px;
        }}
        
        /* MAIN GRID */
        .main-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
        }}
        
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        
        .chart-container {{
            position: relative;
            height: 280px;
        }}
        
        /* CHARTS GRID */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        /* HEATMAP */
        .heatmap-container {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 32px;
        }}
        
        .heatmap-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}
        
        .heatmap-nav {{
            display: flex;
            gap: 8px;
        }}
        
        .heatmap-nav button {{
            background: var(--border);
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .heatmap-nav button:hover {{
            background: var(--text-light);
        }}
        
        .heatmap-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
        }}
        
        .heatmap-cell {{
            aspect-ratio: 1;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid rgba(0,0,0,0.1);
            transition: transform 0.2s;
            color: white;
        }}
        
        .heatmap-cell:hover {{
            transform: scale(1.1);
        }}
        
        .heatmap-empty {{
            background: transparent;
            border: none;
            cursor: default;
        }}
        
        .heatmap-empty:hover {{
            transform: none;
        }}
        
        /* STATS SIDEBAR */
        .stat-item {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }}
        
        .stat-item:last-child {{
            border-bottom: none;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
        }}
        
        .stat-value {{
            font-weight: 600;
        }}
        
        /* MODAL */
        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        
        .modal.open {{
            display: flex;
        }}
        
        .modal-content {{
            background: var(--card);
            border-radius: 12px;
            max-width: 800px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            padding: 32px;
        }}
        
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .modal-date {{
            font-size: 16px;
            font-weight: 600;
        }}
        
        .modal-pnl {{
            font-size: 24px;
            font-weight: 700;
        }}
        
        .modal-close {{
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
        }}
        
        .modal-stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .stat-card {{
            background: var(--border);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}
        
        .stat-card-label {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }}
        
        .stat-card-value {{
            font-size: 18px;
            font-weight: 700;
        }}
        
        /* RESPONSIVE */
        @media (max-width: 1200px) {{
            .metrics {{
                grid-template-columns: repeat(3, 1fr);
            }}
            
            .main-grid {{
                grid-template-columns: 1fr;
            }}
            
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 16px;
            }}
            
            .metrics {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .metric {{
                padding: 16px;
            }}
            
            .metric-value {{
                font-size: 22px;
            }}
            
            .modal-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="header-title">Trading Dashboard</div>
                <div class="header-meta">Since {inception_date_str}</div>
            </div>
            <button class="dark-toggle" onclick="toggleDarkMode()">🌙</button>
        </div>
        
        <!-- METRICS -->
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Account Value</div>
                <div class="metric-value">{current_value_fmt}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Daily P&L</div>
                <div class="metric-value" style="color: {daily_pnl_color}">{daily_pnl_fmt}</div>
                <div class="metric-sub">{daily_pct_fmt}</div>
            </div>
            <div class="metric">
                <div class="metric-label">30-Day Return</div>
                <div class="metric-value" style="color: {return_30d_color}">{return_30d_fmt}</div>
            </div>
            <div class="metric">
                <div class="metric-label">YTD Return</div>
                <div class="metric-value" style="color: {return_ytd_color}">{return_ytd_fmt}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Inception Return</div>
                <div class="metric-value" style="color: {return_inception_color}">{return_inception_fmt}</div>
            </div>
        </div>
        
        <!-- EQUITY CURVE -->
        <div class="main-grid">
            <div class="card">
                <div class="card-title">Equity Curve (60 Days)</div>
                <div class="chart-container">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Performance</div>
                <div class="stat-item">
                    <span class="stat-label">Win Rate</span>
                    <span class="stat-value" style="color: var(--green)">{win_rate_fmt}%</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Best Day</span>
                    <span class="stat-value" style="color: var(--green)">{best_day_fmt}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Worst Day</span>
                    <span class="stat-value" style="color: var(--red)">{worst_day_fmt}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Drawdown</span>
                    <span class="stat-value" style="color: var(--red)">{drawdown_fmt}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Volatility</span>
                    <span class="stat-value">{volatility_fmt}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Trades</span>
                    <span class="stat-value">{trades_total}</span>
                </div>
            </div>
        </div>
        
        <!-- CHARTS GRID -->
        <div class="charts-grid">
            <div class="card">
                <div class="card-title">Entry Time Analysis (PST)</div>
                <div class="chart-container">
                    <canvas id="entryTimeChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Duration vs P&L</div>
                <div class="chart-container">
                    <canvas id="durationChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- MONTHLY HEATMAP -->
        <div class="heatmap-container">
            <div class="heatmap-header">
                <div class="card-title" style="margin: 0;">{month_name_str}</div>
                <div class="heatmap-nav">
                    <button onclick="prevMonth()">← Prev</button>
                    <button onclick="nextMonth()">Next →</button>
                </div>
            </div>
            <div class="heatmap-grid">
                {calendar_cells_html}
            </div>
        </div>
    </div>
    
    <!-- DAY DETAIL MODAL -->
    <div class="modal" id="dayModal">
        <div class="modal-content" style="max-width: 1000px;">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border);">
                <div>
                    <div style="font-size: 14px; color: var(--text-secondary); margin-bottom: 4px;" id="modalDate">Wed, Apr 01, 2026</div>
                    <div style="font-size: 28px; font-weight: 700;" id="modalPnL">-$74.62</div>
                </div>
                <div style="display: flex; gap: 12px;">
                    <button style="background: none; border: 1px solid var(--border); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600;" onclick="alert('Add note coming soon')">+ Add note</button>
                    <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--purple); color: white; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600;">JP</div>
                </div>
                <button class="modal-close" onclick="closeDayDetail()" style="position: absolute; top: 16px; right: 16px;">✕</button>
            </div>
            
            <!-- Summary Section: Chart + Stats Grid -->
            <div style="display: grid; grid-template-columns: 1fr 1.2fr; gap: 24px; margin-bottom: 24px;">
                <!-- Intraday P&L Chart -->
                <div>
                    <div style="font-size: 12px; font-weight: 600; margin-bottom: 12px; color: var(--text-secondary);">Intraday P&L Progression</div>
                    <div style="height: 200px;">
                        <canvas id="intradayChart" style="width: 100% !important; height: 100% !important;"></canvas>
                    </div>
                </div>
                
                <!-- Stats Grid -->
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Total Trades</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statTotalTrades">5</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Gross P&L</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statGrossPnL">$150.00</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Winners/Losers</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statWinLoss">3/2</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Commissions</div>
                        <div style="font-size: 18px; font-weight: 700;">$0.00</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Win Rate</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statWinRate">60%</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Volume</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statVolume">1,500</div>
                    </div>
                    <div style="background: var(--border); padding: 12px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Profit Factor</div>
                        <div style="font-size: 18px; font-weight: 700;" id="statProfitFactor">1.8x</div>
                    </div>
                    <div></div>
                </div>
            </div>
            
            <!-- Trades Table -->
            <div style="margin-bottom: 24px;">
                <div style="font-size: 12px; font-weight: 600; margin-bottom: 12px; color: var(--text-secondary);">Trades</div>
                <div style="overflow-x: auto; border: 1px solid var(--border); border-radius: 8px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: var(--border);">
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Open Time</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Ticker</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Side</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Instrument</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Net P&L</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Net ROI</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">R-Multiple</th>
                                <th style="padding: 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--text-secondary);">Strategy</th>
                            </tr>
                        </thead>
                        <tbody>
                            {modal_trades_table}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="display: flex; gap: 12px; justify-content: flex-end; border-top: 1px solid var(--border); padding-top: 16px;">
                <button style="background: none; border: 1px solid var(--border); padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600;" onclick="closeDayDetail()">Cancel</button>
                <button style="background: var(--purple); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600;" onclick="alert('View details coming soon')">View Details</button>
            </div>
        </div>
    </div>
    
    <script>
        // Dark mode
        function toggleDarkMode() {{
            document.documentElement.classList.toggle('dark');
            localStorage.setItem('darkMode', document.documentElement.classList.contains('dark'));
        }}
        
        if (localStorage.getItem('darkMode') === 'true') {{
            document.documentElement.classList.add('dark');
        }}
        
        // Day detail modal
        const intradayData = {intraday_json};
        
        function openDayDetail(date, pnl, trades) {{
            const winners = Math.floor(trades * 0.6);
            const losers = trades - winners;
            const winRate = (winners / trades * 100).toFixed(1);
            
            document.getElementById('modalDate').textContent = new Date(date).toLocaleDateString('en-US', {{ weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }});
            document.getElementById('modalPnL').textContent = (pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2);
            document.getElementById('modalPnL').style.color = pnl >= 0 ? '#10B981' : '#EF4444';
            document.getElementById('statTotalTrades').textContent = trades;
            document.getElementById('statWinLoss').textContent = winners + ' / ' + losers;
            document.getElementById('statWinRate').textContent = winRate + '%';
            document.getElementById('statGrossPnL').textContent = (pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2);
            document.getElementById('statGrossPnL').style.color = pnl >= 0 ? '#10B981' : '#EF4444';
            
            // Render intraday chart
            renderIntradayChart();
            
            document.getElementById('dayModal').classList.add('open');
        }}
        
        function renderIntradayChart() {{
            const ctx = document.getElementById('intradayChart');
            if (ctx.chart) {{
                ctx.chart.destroy();
            }}
            
            ctx.chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: intradayData.map(d => d.time_label),
                    datasets: [{{
                        label: 'Cumulative P&L',
                        data: intradayData.map(d => d.cumulative_pnl),
                        borderColor: '#EF4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: '#252D3D',
                            borderColor: '#374151',
                            titleColor: '#F1F5F9',
                            bodyColor: '#F1F5F9',
                            padding: 12,
                            displayColors: false,
                            callbacks: {{
                                label: function(context) {{
                                    return 'P&L: $' + context.parsed.y.toFixed(2);
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            grid: {{ color: 'rgba(0,0,0,0.05)' }},
                            ticks: {{ color: '#9CA3AF' }},
                        }},
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{ color: '#9CA3AF' }},
                        }}
                    }}
                }}
            }});
        }}
        
        function closeDayDetail() {{
            document.getElementById('dayModal').classList.remove('open');
        }}
        
        // Month navigation (placeholder)
        function prevMonth() {{
            alert('Previous month functionality coming soon');
        }}
        
        function nextMonth() {{
            alert('Next month functionality coming soon');
        }}
        
        // Helper function to convert minutes to human-readable time
        function formatDuration(minutes) {{
            if (minutes < 60) {{
                return minutes + 'm';
            }}
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            if (mins === 0) {{
                return hours + 'hr';
            }}
            return hours + 'hr' + mins + 'm';
        }}
        
        // Equity chart
        const chartData = {chart_data_json};
        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: chartData.map(d => d.date),
                datasets: [{{
                    data: chartData.map(d => d.value),
                    borderColor: '#6366F1',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#252D3D',
                        borderColor: '#374151',
                        titleColor: '#F1F5F9',
                        bodyColor: '#F1F5F9',
                        padding: 12,
                        displayColors: false,
                    }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(0,0,0,0.05)' }},
                        ticks: {{ color: '#9CA3AF' }},
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#9CA3AF' }},
                    }}
                }}
            }}
        }});
        
        // Entry Time Analysis Chart with PST labels
        const entryTimeLabels = {entry_time_labels_json};
        const entryTimePnLs = {entry_time_pnls_json};
        
        const entryCtx = document.getElementById('entryTimeChart').getContext('2d');
        new Chart(entryCtx, {{
            type: 'bar',
            data: {{
                labels: entryTimeLabels,
                datasets: [{{
                    label: 'Avg P&L',
                    data: entryTimePnLs,
                    backgroundColor: entryTimePnLs.map(v => v >= 0 ? '#10B981' : '#EF4444'),
                    borderRadius: 6,
                    borderSkipped: false,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'x',
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#252D3D',
                        borderColor: '#374151',
                        titleColor: '#F1F5F9',
                        bodyColor: '#F1F5F9',
                        padding: 12,
                        callbacks: {{
                            label: function(context) {{
                                return 'Avg P&L: $' + context.parsed.y.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(0,0,0,0.05)' }},
                        ticks: {{ color: '#9CA3AF' }},
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#9CA3AF' }},
                    }}
                }}
            }}
        }});
        
        // Duration vs P&L Scatter Chart
        const durationData = {duration_vs_pnl_json};
        
        const durationCtx = document.getElementById('durationChart').getContext('2d');
        new Chart(durationCtx, {{
            type: 'scatter',
            data: {{
                datasets: [{{
                    label: 'Trades',
                    data: durationData.map(function(d) {{ return {{ x: d.duration, y: d.pnl }}; }}),
                    backgroundColor: 'rgba(99, 102, 241, 0.6)',
                    borderColor: '#6366F1',
                    borderWidth: 1,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#252D3D',
                        borderColor: '#374151',
                        titleColor: '#F1F5F9',
                        bodyColor: '#F1F5F9',
                        padding: 12,
                        callbacks: {{
                            label: function(context) {{
                                return 'Duration: ' + context.parsed.x + 'min, P&L: $' + context.parsed.y.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        title: {{ display: true, text: 'P&L ($)', color: '#9CA3AF', font: {{ size: 12 }} }},
                        grid: {{ color: 'rgba(0,0,0,0.05)' }},
                        ticks: {{
                            color: '#9CA3AF',
                            callback: function(value) {{
                                return '$' + value.toFixed(0);
                            }}
                        }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Trade Duration', color: '#9CA3AF', font: {{ size: 12 }} }},
                        grid: {{ color: 'rgba(0,0,0,0.05)' }},
                        ticks: {{
                            color: '#9CA3AF',
                            callback: function(value) {{
                                return formatDuration(value);
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
""".format(
        inception_date_str=inception_date.strftime('%b %d, %Y'),
        current_value_fmt=fmt_currency(current_value),
        daily_pnl_fmt=fmt_currency(daily_pnl),
        daily_pnl_color=color_for_value(daily_pnl),
        daily_pct_fmt=fmt_pct(daily_pct),
        return_30d_fmt=fmt_pct(return_30d_pct),
        return_30d_color=color_for_value(return_30d),
        return_ytd_fmt=fmt_pct(return_ytd_pct),
        return_ytd_color=color_for_value(return_ytd),
        return_inception_fmt=fmt_pct(return_inception_pct),
        return_inception_color=color_for_value(return_inception),
        win_rate_fmt=f"{win_rate:.1f}",
        best_day_fmt=fmt_pct(best_day),
        worst_day_fmt=fmt_pct(worst_day),
        drawdown_fmt=fmt_pct(drawdown),
        volatility_fmt=f"{std_daily:.2f}%",
        trades_total=trades_total,
        month_name_str=month_name,
        calendar_cells_html=calendar_cells_html,
        chart_data_json=chart_data_json,
        entry_time_labels_json=entry_time_labels_json,
        entry_time_pnls_json=entry_time_pnls_json,
        duration_vs_pnl_json=duration_vs_pnl_json,
        modal_trades_table=trades_table_html,
        intraday_json=intraday_json,
    )
    
    DASHBOARD_FILE.write_text(html_content)
    print(f"✓ Clean dashboard generated: {DASHBOARD_FILE}")
    return True

if __name__ == '__main__':
    try:
        generate_dashboard()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
