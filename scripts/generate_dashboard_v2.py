#!/usr/bin/env python3
"""
Premium investor dashboard generator - redesigned for institutional quality.
- Better color palette and typography
- More visualizations (distribution, win rate, daily bars)
- Cleaner hierarchy and layout
- Responsive design prioritizing investor experience
"""

import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from string import Template

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
REPORT_DIR = REPO_ROOT / "reports"
DASHBOARD_FILE = REPO_ROOT / "index.html"

# Premium color palette - investor grade
COLORS = {
    "bg_primary": "#0F172A",      # Deep navy
    "bg_secondary": "#1A2344",    # Slightly lighter navy
    "bg_tertiary": "#252F45",     # Light navy
    "border": "#334155",          # Slate border
    "text_primary": "#F1F5F9",    # Off-white
    "text_secondary": "#94A3B8",  # Slate gray
    "positive": "#10B981",        # Emerald green
    "negative": "#DC2626",        # Deep red
    "neutral": "#6366F1",         # Indigo
    "accent": "#F59E0B",          # Amber for highlights
    "chart_pos": "#10B981",
    "chart_neg": "#DC2626",
}

def load_balance_history():
    """Load balance history from tracker"""
    if not TRACKER_FILE.exists():
        raise FileNotFoundError(f"Balance tracker not found at {TRACKER_FILE}")
    
    with TRACKER_FILE.open("r") as f:
        raw = json.load(f)
    
    items = sorted(
        ((datetime.strptime(date_str, "%Y-%m-%d"), float(value)) for date_str, value in raw.items()),
        key=lambda item: item[0],
    )
    
    # Ensure inception date exists
    if not any(date_obj == INCEPTION_TARGET for date_obj, _ in items):
        items.insert(0, (INCEPTION_TARGET, INCEPTION_BALANCE))
    
    return items

def find_latest_report():
    """Find the most recent trading report"""
    if not REPORT_DIR.exists():
        return None, ""
    
    files = sorted(REPORT_DIR.glob("*-trading-report.md"))
    if not files:
        return None, ""
    
    latest = files[-1]
    return latest, latest.read_text()

def parse_report_metrics(report_text):
    """Extract metrics from markdown report"""
    metrics = {}
    patterns = {
        "current_value": r"Current Value:\s*\$([\d,]+\.\d{2})",
        "prior_close": r"Prior Close:\s*\$([\d,]+\.\d{2})",
        "cash_position": r"Cash Position:\s*\$([\d,]+\.\d{2})",
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
            elif key in {"current_value", "prior_close", "cash_position"}:
                metrics[key] = float(value.replace(",", ""))
            else:
                metrics[key] = value
        else:
            metrics[key] = None
    
    return metrics

def calculate_distribution_buckets(daily_returns):
    """Calculate return distribution for histogram"""
    if not daily_returns:
        return []
    
    # Bucketing: -5%, -2%, -1%, 0%, 1%, 2%, 5%, 10%+
    buckets = [
        {"label": "< -5%", "min": -100, "max": -5, "count": 0},
        {"label": "-5% to -2%", "min": -5, "max": -2, "count": 0},
        {"label": "-2% to -1%", "min": -2, "max": -1, "count": 0},
        {"label": "-1% to 0%", "min": -1, "max": 0, "count": 0},
        {"label": "0% to 1%", "min": 0, "max": 1, "count": 0},
        {"label": "1% to 2%", "min": 1, "max": 2, "count": 0},
        {"label": "2% to 5%", "min": 2, "max": 5, "count": 0},
        {"label": "> 5%", "min": 5, "max": 100, "count": 0},
    ]
    
    for ret in daily_returns:
        for bucket in buckets:
            if bucket["min"] <= ret < bucket["max"]:
                bucket["count"] += 1
                break
    
    return buckets

def generate_dashboard():
    """Generate premium investor dashboard"""
    
    history = load_balance_history()
    latest_file, report_text = find_latest_report()
    report_metrics = parse_report_metrics(report_text) if report_text else {}
    
    # Core metrics
    latest_date, current_value = history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = INCEPTION_BALANCE
    
    # Calculate daily returns
    daily_returns = []
    for i in range(1, len(history)):
        prev_val = history[i-1][1]
        curr_val = history[i][1]
        if prev_val:
            daily_pct = ((curr_val - prev_val) / prev_val) * 100
            daily_returns.append(daily_pct)
    
    # Rolling periods
    trailing_30 = history[-30:] if len(history) >= 30 else history
    trailing_60 = history[-60:] if len(history) >= 60 else history
    
    # Period baselines
    val_30d_ago = history[-30][1] if len(history) >= 30 else inception_value
    val_ytd = next((v for d, v in history if d.year == datetime.now().year), inception_value)
    
    # Calculate returns
    daily_pnl = current_value - history[-2][1] if len(history) > 1 else 0
    daily_pct = (daily_pnl / history[-2][1] * 100) if len(history) > 1 and history[-2][1] else 0
    
    return_30d = current_value - val_30d_ago
    return_30d_pct = (return_30d / val_30d_ago * 100) if val_30d_ago else 0
    
    return_ytd = current_value - val_ytd
    return_ytd_pct = (return_ytd / val_ytd * 100) if val_ytd else 0
    
    return_inception = current_value - inception_value
    return_inception_pct = (return_inception / inception_value * 100) if inception_value else 0
    
    # Volatility and stats
    if daily_returns:
        avg_daily = mean(daily_returns)
        std_daily = stdev(daily_returns) if len(daily_returns) > 1 else 0
        positive_days = sum(1 for r in daily_returns if r > 0)
        win_rate = (positive_days / len(daily_returns) * 100) if daily_returns else 0
        best_day = max(daily_returns)
        worst_day = min(daily_returns)
    else:
        avg_daily = std_daily = positive_days = win_rate = best_day = worst_day = 0
    
    # All-time stats
    all_time_high = max(v for _, v in history)
    all_time_high_date = next(d for d, v in history if v == all_time_high)
    drawdown = ((current_value - all_time_high) / all_time_high * 100) if all_time_high else 0
    
    # Distribution
    dist_buckets = calculate_distribution_buckets(daily_returns)
    max_bucket_count = max(b["count"] for b in dist_buckets) if dist_buckets else 1
    
    # Trade stats
    trades_7d = report_metrics.get("filled_7d", 0) or 0
    trades_today = report_metrics.get("today_trades", 0) or 0
    trades_total = report_metrics.get("all_filled", 157) or 157
    
    # Format values
    def fmt_currency(v):
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    
    def fmt_pct(v):
        return f"{v:+.2f}%"
    
    def fmt_color(v):
        if v > 0:
            return COLORS["positive"]
        elif v < 0:
            return COLORS["negative"]
        return COLORS["neutral"]
    
    # Build chart data for equity curve
    chart_data = [
        {"date": d.strftime("%Y-%m-%d"), "label": d.strftime("%b %d"), "value": round(v, 2)}
        for d, v in history
    ]
    
    # Build distribution bars
    dist_bars = []
    for bucket in dist_buckets:
        pct = (bucket["count"] / max_bucket_count * 100) if max_bucket_count > 0 else 0
        color = COLORS["positive"] if "to 1%" in bucket["label"] or (bucket["min"] > 0) else COLORS["negative"]
        dist_bars.append({
            "label": bucket["label"],
            "count": bucket["count"],
            "pct": pct,
            "color": color,
        })
    
    # HTML Template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard — {latest_date.strftime('%B %d, %Y')}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, {COLORS['bg_primary']} 0%, #0a0f1f 100%);
            color: {COLORS['text_primary']};
            overflow-x: hidden;
            width: 100%;
            min-height: 100vh;
            padding: 32px 24px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }}
        
        /* HERO SECTION */
        .hero {{
            background: linear-gradient(135deg, {COLORS['bg_secondary']} 0%, {COLORS['bg_tertiary']} 100%);
            border: 1px solid {COLORS['border']};
            border-radius: 24px;
            padding: 48px;
            margin-bottom: 32px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 48px;
            align-items: center;
        }}
        
        .hero-left {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        .hero-label {{
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: {COLORS['accent']};
        }}
        
        .hero-value {{
            font-size: 64px;
            font-weight: 700;
            letter-spacing: -2px;
            line-height: 1;
        }}
        
        .hero-date {{
            font-size: 14px;
            color: {COLORS['text_secondary']};
        }}
        
        .hero-right {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        
        .stat-badge {{
            background: {COLORS['bg_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 24px;
            text-align: center;
        }}
        
        .stat-badge-label {{
            font-size: 12px;
            color: {COLORS['text_secondary']};
            margin-bottom: 8px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.8px;
        }}
        
        .stat-badge-value {{
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
        }}
        
        .stat-badge-sub {{
            font-size: 12px;
            color: {COLORS['text_secondary']};
            margin-top: 8px;
        }}
        
        /* METRICS GRID */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 32px;
        }}
        
        .metric-card {{
            background: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 24px;
        }}
        
        .metric-card-label {{
            font-size: 12px;
            color: {COLORS['text_secondary']};
            margin-bottom: 12px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.8px;
        }}
        
        .metric-card-value {{
            font-size: 28px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 8px;
        }}
        
        .metric-card-sub {{
            font-size: 12px;
            color: {COLORS['text_secondary']};
        }}
        
        /* CHARTS SECTION */
        .charts-section {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        .chart-panel {{
            background: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 28px;
        }}
        
        .chart-title {{
            font-size: 14px;
            font-weight: 600;
            color: {COLORS['text_primary']};
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        
        .chart-container {{
            position: relative;
            height: 320px;
            margin-bottom: 16px;
        }}
        
        .distribution-chart {{
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            gap: 8px;
            height: 240px;
        }}
        
        .dist-bar {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        
        .dist-bar-fill {{
            width: 100%;
            border-radius: 4px;
            transition: opacity 0.2s;
        }}
        
        .dist-bar-label {{
            font-size: 10px;
            color: {COLORS['text_secondary']};
            text-align: center;
            width: 100%;
        }}
        
        .dist-bar-count {{
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        }}
        
        /* EXECUTION SUMMARY */
        .execution-section {{
            background: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 28px;
        }}
        
        .exec-title {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: {COLORS['text_primary']};
            margin-bottom: 20px;
        }}
        
        .exec-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }}
        
        .exec-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .exec-label {{
            font-size: 12px;
            color: {COLORS['text_secondary']};
        }}
        
        .exec-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        
        /* RESPONSIVE */
        @media (max-width: 1200px) {{
            .hero {{
                grid-template-columns: 1fr;
                padding: 36px;
                gap: 32px;
            }}
            
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .charts-section {{
                grid-template-columns: 1fr;
            }}
            
            .exec-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 16px 12px;
            }}
            
            .hero {{
                padding: 24px;
                gap: 24px;
            }}
            
            .hero-value {{
                font-size: 44px;
            }}
            
            .hero-right {{
                grid-template-columns: 1fr;
            }}
            
            .metrics-grid {{
                grid-template-columns: 1fr;
                gap: 12px;
            }}
            
            .metric-card {{
                padding: 16px;
            }}
            
            .metric-card-value {{
                font-size: 24px;
            }}
            
            .chart-panel {{
                padding: 20px;
            }}
            
            .exec-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{
                padding: 12px;
            }}
            
            .hero {{
                padding: 20px;
                border-radius: 16px;
            }}
            
            .hero-value {{
                font-size: 36px;
            }}
            
            .stat-badge {{
                padding: 16px;
            }}
            
            .stat-badge-value {{
                font-size: 24px;
            }}
            
            .metrics-grid {{
                gap: 10px;
            }}
            
            .metric-card {{
                padding: 12px;
            }}
            
            .metric-card-label {{
                font-size: 11px;
            }}
            
            .metric-card-value {{
                font-size: 20px;
            }}
            
            .metric-card-sub {{
                font-size: 11px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HERO -->
        <div class="hero">
            <div class="hero-left">
                <div class="hero-label">Net Liquidating Value</div>
                <div class="hero-value">{fmt_currency(current_value)}</div>
                <div class="hero-date">As of {latest_date.strftime('%B %d, %Y')}</div>
            </div>
            <div class="hero-right">
                <div class="stat-badge">
                    <div class="stat-badge-label">Daily P&L</div>
                    <div class="stat-badge-value" style="color: {fmt_color(daily_pnl)}">{fmt_currency(daily_pnl)}</div>
                    <div class="stat-badge-sub">{fmt_pct(daily_pct)}</div>
                </div>
                <div class="stat-badge">
                    <div class="stat-badge-label">Inception Return</div>
                    <div class="stat-badge-value" style="color: {fmt_color(return_inception)}">{fmt_pct(return_inception_pct)}</div>
                    <div class="stat-badge-sub">{fmt_currency(return_inception)}</div>
                </div>
                <div class="stat-badge">
                    <div class="stat-badge-label">All-Time High</div>
                    <div class="stat-badge-value">{fmt_currency(all_time_high)}</div>
                    <div class="stat-badge-sub">{all_time_high_date.strftime('%b %d, %Y')}</div>
                </div>
                <div class="stat-badge">
                    <div class="stat-badge-label">Drawdown</div>
                    <div class="stat-badge-value" style="color: {fmt_color(drawdown)}">{fmt_pct(drawdown)}</div>
                    <div class="stat-badge-sub">from peak</div>
                </div>
            </div>
        </div>
        
        <!-- METRICS GRID -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-card-label">30-Day Return</div>
                <div class="metric-card-value" style="color: {fmt_color(return_30d)}">{fmt_pct(return_30d_pct)}</div>
                <div class="metric-card-sub">{fmt_currency(return_30d)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-card-label">YTD Return</div>
                <div class="metric-card-value" style="color: {fmt_color(return_ytd)}">{fmt_pct(return_ytd_pct)}</div>
                <div class="metric-card-sub">{fmt_currency(return_ytd)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-card-label">Win Rate</div>
                <div class="metric-card-value" style="color: {COLORS['positive']}">{win_rate:.1f}%</div>
                <div class="metric-card-sub">{positive_days} of {len(daily_returns)} days</div>
            </div>
            <div class="metric-card">
                <div class="metric-card-label">Avg Daily Move</div>
                <div class="metric-card-value">{abs(avg_daily):.2f}%</div>
                <div class="metric-card-sub">σ {std_daily:.2f}%</div>
            </div>
        </div>
        
        <!-- CHARTS -->
        <div class="charts-section">
            <div class="chart-panel">
                <div class="chart-title">Equity Curve</div>
                <div class="chart-container">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>
            <div class="chart-panel">
                <div class="chart-title">Return Distribution</div>
                <div class="distribution-chart">
                    {''.join(f'''
                    <div class="dist-bar">
                        <div class="dist-bar-fill" style="height: {b['pct']}%; background-color: {b['color']};"></div>
                        <div class="dist-bar-count">{b['count']}</div>
                        <div class="dist-bar-label">{b['label']}</div>
                    </div>
                    ''' for b in dist_bars)}
                </div>
            </div>
        </div>
        
        <!-- EXECUTION SUMMARY (BOTTOM) -->
        <div class="execution-section">
            <div class="exec-title">Trade Summary</div>
            <div class="exec-grid">
                <div class="exec-item">
                    <div class="exec-label">Total Trades (Inception)</div>
                    <div class="exec-value">{trades_total}</div>
                </div>
                <div class="exec-item">
                    <div class="exec-label">This Week</div>
                    <div class="exec-value">{trades_7d}</div>
                </div>
                <div class="exec-item">
                    <div class="exec-label">Today</div>
                    <div class="exec-value">{trades_today}</div>
                </div>
                <div class="exec-item">
                    <div class="exec-label">Best Day</div>
                    <div class="exec-value" style="color: {COLORS['positive']}">{fmt_pct(best_day)}</div>
                </div>
                <div class="exec-item">
                    <div class="exec-label">Worst Day</div>
                    <div class="exec-value" style="color: {COLORS['negative']}">{fmt_pct(worst_day)}</div>
                </div>
                <div class="exec-item">
                    <div class="exec-label">Inception Date</div>
                    <div class="exec-value">{inception_date.strftime('%b %d, %Y')}</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const chartData = {json.dumps(chart_data)};
        
        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: chartData.map(d => d.label),
                datasets: [{{
                    label: 'Account Value',
                    data: chartData.map(d => d.value),
                    borderColor: '{COLORS['accent']}',
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
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
                        backgroundColor: '{COLORS['bg_primary']}',
                        borderColor: '{COLORS['border']}',
                        borderWidth: 1,
                        titleColor: '{COLORS['text_primary']}',
                        bodyColor: '{COLORS['text_primary']}',
                        padding: 12,
                        displayColors: false,
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        grid: {{ color: '{COLORS['border']}', drawBorder: false }},
                        ticks: {{ color: '{COLORS['text_secondary']}' }},
                    }},
                    x: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{ color: '{COLORS['text_secondary']}' }},
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    DASHBOARD_FILE.write_text(html_template)
    print(f"✓ Premium dashboard generated: {DASHBOARD_FILE}")
    return True

if __name__ == '__main__':
    try:
        generate_dashboard()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
