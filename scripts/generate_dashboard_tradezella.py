#!/usr/bin/env python3
"""
TradeZella-inspired trading dashboard.
- Clean, minimal widget-based layout
- Focus on key performance metrics
- Professional institutional design
- Emphasis on trade analysis and performance
"""

import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
REPORT_DIR = REPO_ROOT / "reports"
DASHBOARD_FILE = REPO_ROOT / "index.html"

# TradeZella-inspired color palette
COLORS = {
    "bg": "#FFFFFF",
    "bg_secondary": "#F8F9FA",
    "bg_tertiary": "#EEF0F2",
    "border": "#E0E3E8",
    "text_primary": "#1A1D23",
    "text_secondary": "#6B7280",
    "text_light": "#9CA3AF",
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral": "#6366F1",
    "accent": "#F59E0B",
    "bg_positive": "#ECFDF5",
    "bg_negative": "#FEF2F2",
}

def load_balance_history():
    if not TRACKER_FILE.exists():
        raise FileNotFoundError(f"Balance tracker not found")
    
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

def generate_dashboard():
    history = load_balance_history()
    _, report_text = find_latest_report()
    report_metrics = parse_report_metrics(report_text) if report_text else {}
    
    latest_date, current_value = history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = INCEPTION_BALANCE
    
    # Calculate daily returns
    daily_returns = []
    for i in range(1, len(history)):
        prev = history[i-1][1]
        curr = history[i][1]
        if prev:
            daily_returns.append(((curr - prev) / prev) * 100)
    
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
    
    # All-time
    all_time_high = max(v for _, v in history)
    drawdown = ((current_value - all_time_high) / all_time_high * 100) if all_time_high else 0
    
    # Trades
    trades_7d = report_metrics.get("filled_7d", 0) or 0
    trades_today = report_metrics.get("today_trades", 0) or 0
    trades_total = report_metrics.get("all_filled", 157) or 157
    
    # Chart data
    chart_data = [
        {"date": d.strftime("%b %d"), "value": round(v, 0)}
        for d, v in history[-60:]  # Last 60 days
    ]
    
    def fmt_currency(v):
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    
    def fmt_pct(v):
        return f"{v:+.2f}%"
    
    def color_positive(v):
        return COLORS["positive"] if v >= 0 else COLORS["negative"]
    
    def bg_positive(v):
        return COLORS["bg_positive"] if v >= 0 else COLORS["bg_negative"]
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: {COLORS['bg']};
            color: {COLORS['text_primary']};
            line-height: 1.6;
        }}
        
        .header {{
            background: {COLORS['bg_secondary']};
            border-bottom: 1px solid {COLORS['border']};
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .header-title {{
            font-size: 20px;
            font-weight: 600;
        }}
        
        .header-meta {{
            font-size: 13px;
            color: {COLORS['text_light']};
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 32px;
        }}
        
        /* TOP METRICS ROW */
        .metrics-row {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        
        .metric {{
            background: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
            padding: 24px;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        
        .metric-label {{
            font-size: 12px;
            font-weight: 600;
            color: {COLORS['text_secondary']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        
        .metric-value {{
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 8px;
        }}
        
        .metric-sub {{
            font-size: 13px;
            color: {COLORS['text_light']};
        }}
        
        /* MAIN GRID */
        .main-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        .card {{
            background: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
            padding: 24px;
        }}
        
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 20px;
            color: {COLORS['text_primary']};
        }}
        
        .chart-container {{
            position: relative;
            height: 320px;
        }}
        
        /* SIDEBAR STATS */
        .stat-group {{
            margin-bottom: 24px;
        }}
        
        .stat-group-title {{
            font-size: 11px;
            font-weight: 700;
            color: {COLORS['text_light']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        
        .stat-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid {COLORS['border']};
            font-size: 13px;
        }}
        
        .stat-item:last-child {{
            border-bottom: none;
        }}
        
        .stat-label {{
            color: {COLORS['text_secondary']};
        }}
        
        .stat-value {{
            font-weight: 600;
            color: {COLORS['text_primary']};
        }}
        
        /* TRADES GRID */
        .trades-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        
        .trade-card {{
            background: {COLORS['bg_tertiary']};
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        
        .trade-label {{
            font-size: 11px;
            color: {COLORS['text_light']};
            margin-bottom: 8px;
            text-transform: uppercase;
            font-weight: 600;
        }}
        
        .trade-value {{
            font-size: 28px;
            font-weight: 700;
            color: {COLORS['text_primary']};
        }}
        
        /* RESPONSIVE */
        @media (max-width: 1200px) {{
            .metrics-row {{
                grid-template-columns: repeat(3, 1fr);
            }}
            
            .main-grid {{
                grid-template-columns: 1fr;
            }}
            
            .trades-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        
        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
                gap: 10px;
                padding: 16px;
            }}
            
            .container {{
                padding: 16px;
            }}
            
            .metrics-row {{
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                margin-bottom: 24px;
            }}
            
            .metric {{
                padding: 16px;
                min-height: 100px;
            }}
            
            .metric-value {{
                font-size: 24px;
            }}
            
            .card {{
                padding: 16px;
            }}
            
            .chart-container {{
                height: 240px;
            }}
            
            .trades-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{
                font-size: 14px;
            }}
            
            .header {{
                padding: 12px;
            }}
            
            .container {{
                padding: 12px;
            }}
            
            .metrics-row {{
                grid-template-columns: 1fr;
                gap: 8px;
            }}
            
            .metric {{
                padding: 12px;
                min-height: 90px;
            }}
            
            .metric-value {{
                font-size: 20px;
            }}
            
            .metric-label {{
                font-size: 11px;
            }}
            
            .metric-sub {{
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="header-title">Trading Dashboard</div>
            <div class="header-meta">As of {latest_date.strftime('%B %d, %Y')}</div>
        </div>
        <div class="header-meta">View: Dollars</div>
    </div>
    
    <div class="container">
        <!-- KEY METRICS -->
        <div class="metrics-row">
            <div class="metric">
                <div class="metric-label">Account Value</div>
                <div class="metric-value">{fmt_currency(current_value)}</div>
                <div class="metric-sub">NLV</div>
            </div>
            <div class="metric">
                <div class="metric-label">Daily P&L</div>
                <div class="metric-value" style="color: {color_positive(daily_pnl)}">{fmt_currency(daily_pnl)}</div>
                <div class="metric-sub">{fmt_pct(daily_pct)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">30-Day Return</div>
                <div class="metric-value" style="color: {color_positive(return_30d)}">{fmt_pct(return_30d_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_30d)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">YTD Return</div>
                <div class="metric-value" style="color: {color_positive(return_ytd)}">{fmt_pct(return_ytd_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_ytd)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Inception Return</div>
                <div class="metric-value" style="color: {color_positive(return_inception)}">{fmt_pct(return_inception_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_inception)}</div>
            </div>
        </div>
        
        <!-- MAIN CONTENT -->
        <div class="main-grid">
            <div class="card">
                <div class="card-title">Equity Curve (60 Days)</div>
                <div class="chart-container">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="stat-group">
                    <div class="stat-group-title">Performance</div>
                    <div class="stat-item">
                        <span class="stat-label">Win Rate</span>
                        <span class="stat-value" style="color: {COLORS['positive']}">{win_rate:.1f}%</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Avg Daily Move</span>
                        <span class="stat-value">{abs(avg_daily):.2f}%</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Volatility</span>
                        <span class="stat-value">{std_daily:.2f}%</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Best Day</span>
                        <span class="stat-value" style="color: {COLORS['positive']}">{fmt_pct(best_day)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Worst Day</span>
                        <span class="stat-value" style="color: {COLORS['negative']}">{fmt_pct(worst_day)}</span>
                    </div>
                </div>
                
                <div class="stat-group">
                    <div class="stat-group-title">Risk</div>
                    <div class="stat-item">
                        <span class="stat-label">Drawdown</span>
                        <span class="stat-value" style="color: {COLORS['negative']}">{fmt_pct(drawdown)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">All-Time High</span>
                        <span class="stat-value">{fmt_currency(all_time_high)}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- TRADES SECTION -->
        <div class="card">
            <div class="card-title">Trade Activity</div>
            <div class="trades-grid">
                <div class="trade-card">
                    <div class="trade-label">Total Trades</div>
                    <div class="trade-value">{trades_total}</div>
                </div>
                <div class="trade-card">
                    <div class="trade-label">This Week</div>
                    <div class="trade-value">{trades_7d}</div>
                </div>
                <div class="trade-card">
                    <div class="trade-label">Today</div>
                    <div class="trade-value">{trades_today}</div>
                </div>
                <div class="trade-card">
                    <div class="trade-label">Positive Days</div>
                    <div class="trade-value" style="color: {COLORS['positive']}">{positive_days}</div>
                </div>
                <div class="trade-card">
                    <div class="trade-label">Inception</div>
                    <div class="trade-value">{inception_date.strftime('%b %d')}</div>
                </div>
                <div class="trade-card">
                    <div class="trade-label">Win Rate</div>
                    <div class="trade-value">{win_rate:.0f}%</div>
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
                labels: chartData.map(d => d.date),
                datasets: [{{
                    label: 'Account Value',
                    data: chartData.map(d => d.value),
                    borderColor: '{COLORS['neutral']}',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointBackgroundColor: '{COLORS['neutral']}',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '{COLORS['bg_secondary']}',
                        borderColor: '{COLORS['border']}',
                        borderWidth: 1,
                        titleColor: '{COLORS['text_primary']}',
                        bodyColor: '{COLORS['text_primary']}',
                        padding: 12,
                        displayColors: false,
                        cornerRadius: 6,
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        grid: {{ color: '{COLORS['border']}', drawBorder: false }},
                        ticks: {{ color: '{COLORS['text_light']}', font: {{ size: 12 }} }},
                    }},
                    x: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{ color: '{COLORS['text_light']}', font: {{ size: 12 }} }},
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    DASHBOARD_FILE.write_text(html_content)
    print(f"✓ TradeZella-inspired dashboard generated: {DASHBOARD_FILE}")
    return True

if __name__ == '__main__':
    try:
        generate_dashboard()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
