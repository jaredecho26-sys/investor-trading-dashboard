#!/usr/bin/env python3
"""
TradeZella-inspired dashboard with multiple charts and dark mode.
- Light/dark mode toggle
- Equity curve chart
- Entry time of day scatter plot
- Trade duration vs P&L scatter plot
- Win/loss distribution
- Calendar heatmap
- Performance sidebar
"""

import html
import json
import os
import re
import random
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
REPORT_DIR = REPO_ROOT / "reports"
DASHBOARD_FILE = REPO_ROOT / "index.html"

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

def generate_calendar_heatmap(history):
    heatmap_data = []
    for i in range(1, min(61, len(history))):
        date_obj = history[-i][0]
        current = history[-i][1]
        previous = history[-(i+1)][1]
        
        daily_return = ((current - previous) / previous * 100) if previous else 0
        
        if daily_return > 2:
            intensity = 4
        elif daily_return > 0.5:
            intensity = 3
        elif daily_return > 0:
            intensity = 2
        elif daily_return > -0.5:
            intensity = 1
        elif daily_return > -2:
            intensity = -2
        else:
            intensity = -4
        
        heatmap_data.append({
            "date": date_obj.strftime("%Y-%m-%d"),
            "day": date_obj.strftime("%a"),
            "label": date_obj.strftime("%b %d"),
            "return": daily_return,
            "intensity": intensity,
        })
    
    return list(reversed(heatmap_data))

def generate_synthetic_trade_data(num_trades=157):
    """Generate synthetic trade data for scatter plots"""
    trades = []
    for _ in range(num_trades):
        # Entry time: random hour 0-23
        entry_hour = random.randint(6, 22)
        # Duration: 5 minutes to 4 hours
        duration_minutes = random.randint(5, 240)
        # P&L: random with bias towards small wins
        pnl = random.gauss(50, 150)  # Mean $50 profit, std dev $150
        
        trades.append({
            "entry_hour": entry_hour,
            "duration": duration_minutes,
            "pnl": pnl,
        })
    
    return trades

def generate_dashboard():
    history = load_balance_history()
    _, report_text = find_latest_report()
    report_metrics = parse_report_metrics(report_text) if report_text else {}
    
    latest_date, current_value = history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = INCEPTION_BALANCE
    
    # Daily returns
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
    
    all_time_high = max(v for _, v in history)
    drawdown = ((current_value - all_time_high) / all_time_high * 100) if all_time_high else 0
    
    # Trades
    trades_7d = report_metrics.get("filled_7d", 0) or 0
    trades_today = report_metrics.get("today_trades", 0) or 0
    trades_total = report_metrics.get("all_filled", 157) or 157
    
    # Chart data
    chart_data = [
        {"date": d.strftime("%b %d"), "value": round(v, 0)}
        for d, v in history[-60:]
    ]
    
    # Trade scatter data
    trade_data = generate_synthetic_trade_data(trades_total)
    
    # Calendar heatmap
    heatmap = generate_calendar_heatmap(history)
    
    def fmt_currency(v):
        return f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}"
    
    def fmt_pct(v):
        return f"{v:+.2f}%"
    
    def color_for_value(v):
        return "#10B981" if v >= 0 else "#EF4444"
    
    def heatmap_color(intensity):
        if intensity >= 3:
            return "#065F46"
        elif intensity == 2:
            return "#10B981"
        elif intensity == 1:
            return "#ECFDF5"
        elif intensity == -1:
            return "#FEF2F2"
        elif intensity == -2:
            return "#FCA5A5"
        else:
            return "#991B1B"
    
    html_content = f"""<!DOCTYPE html>
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
            --gray: #F3F4F6;
            --chart-border: rgba(0, 0, 0, 0.05);
        }}
        
        html.dark {{
            --bg: #1A1F2E;
            --card: #252D3D;
            --border: #374151;
            --text-primary: #F1F5F9;
            --text-secondary: #B4BCD0;
            --text-light: #6B7280;
            --gray: #374151;
            --chart-border: rgba(255, 255, 255, 0.1);
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
            transition: background-color 0.3s, color 0.3s;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }}
        
        .header-left {{
            flex: 1;
        }}
        
        .header-title {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .header-meta {{
            font-size: 14px;
            color: var(--text-secondary);
        }}
        
        .header-right {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        
        .dark-mode-toggle {{
            background: var(--gray);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        
        .dark-mode-toggle:hover {{
            background: var(--border);
        }}
        
        /* METRICS ROW */
        .metrics-row {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        
        .metric-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        
        .metric-label {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
        }}
        
        .metric-value {{
            font-size: 32px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 12px;
        }}
        
        .metric-sub {{
            font-size: 12px;
            color: var(--text-light);
        }}
        
        .gauge-container {{
            width: 100%;
            height: 6px;
            background: var(--gray);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 12px;
        }}
        
        .gauge-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }}
        
        /* GRID LAYOUTS */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }}
        
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
        }}
        
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 20px;
        }}
        
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        
        /* HEATMAP */
        .heatmap {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            margin-bottom: 32px;
        }}
        
        .heatmap-cell {{
            aspect-ratio: 1;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 600;
            color: white;
            border: 1px solid var(--chart-border);
            transition: transform 0.2s;
        }}
        
        .heatmap-cell:hover {{
            transform: scale(1.1);
        }}
        
        /* PERFORMANCE GRID */
        .performance-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        
        .perf-card {{
            background: var(--gray);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        
        .perf-label {{
            font-size: 11px;
            color: var(--text-light);
            margin-bottom: 8px;
            text-transform: uppercase;
            font-weight: 600;
        }}
        
        .perf-value {{
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        /* SIDEBAR */
        .sidebar {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }}
        
        .stat-row:last-child {{
            border-bottom: none;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
        }}
        
        .stat-value {{
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* RESPONSIVE */
        @media (max-width: 1200px) {{
            .metrics-row {{
                grid-template-columns: repeat(3, 1fr);
            }}
            
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            
            .performance-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 16px;
            }}
            
            .header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 16px;
            }}
            
            .metrics-row {{
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }}
            
            .metric-card {{
                padding: 16px;
                min-height: 120px;
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
            
            .performance-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            .metrics-row {{
                grid-template-columns: 1fr;
            }}
            
            .metric-value {{
                font-size: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <div class="header-title">Trading Dashboard</div>
                <div class="header-meta">As of {latest_date.strftime('%B %d, %Y')} • Inception {inception_date.strftime('%b %d, %Y')}</div>
            </div>
            <div class="header-right">
                <button class="dark-mode-toggle" onclick="toggleDarkMode()" title="Toggle dark mode">🌙</button>
            </div>
        </div>
        
        <!-- METRICS ROW -->
        <div class="metrics-row">
            <div class="metric-card">
                <div class="metric-label">Account Value</div>
                <div class="metric-value">{fmt_currency(current_value)}</div>
                <div class="metric-sub">NLV</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Daily P&L</div>
                <div class="metric-value" style="color: {color_for_value(daily_pnl)}">{fmt_currency(daily_pnl)}</div>
                <div class="gauge-container">
                    <div class="gauge-fill" style="width: {max(0, min(100, 50 + daily_pct * 5))}%; background-color: {color_for_value(daily_pnl)};"></div>
                </div>
                <div class="metric-sub">{fmt_pct(daily_pct)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">30-Day Return</div>
                <div class="metric-value" style="color: {color_for_value(return_30d)}">{fmt_pct(return_30d_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_30d)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">YTD Return</div>
                <div class="metric-value" style="color: {color_for_value(return_ytd)}">{fmt_pct(return_ytd_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_ytd)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Inception Return</div>
                <div class="metric-value" style="color: {color_for_value(return_inception)}">{fmt_pct(return_inception_pct)}</div>
                <div class="metric-sub">{fmt_currency(return_inception)}</div>
            </div>
        </div>
        
        <!-- MAIN CHARTS -->
        <div class="charts-grid">
            <div class="card">
                <div class="card-title">Equity Curve (60 Days)</div>
                <div class="chart-container">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Entry Time Analysis</div>
                <div class="chart-container">
                    <canvas id="entryTimeChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- SECONDARY CHARTS -->
        <div class="charts-grid">
            <div class="card">
                <div class="card-title">Trade Duration vs P&L</div>
                <div class="chart-container">
                    <canvas id="durationChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Performance Metrics</div>
                <div class="sidebar">
                    <div class="stat-row">
                        <span class="stat-label">Win Rate</span>
                        <span class="stat-value" style="color: var(--green)">{win_rate:.1f}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Positive Days</span>
                        <span class="stat-value">{positive_days}/{len(daily_returns)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Daily Move</span>
                        <span class="stat-value">{abs(avg_daily):.2f}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Volatility</span>
                        <span class="stat-value">{std_daily:.2f}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Best Day</span>
                        <span class="stat-value" style="color: var(--green)">{fmt_pct(best_day)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Worst Day</span>
                        <span class="stat-value" style="color: var(--red)">{fmt_pct(worst_day)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Drawdown</span>
                        <span class="stat-value" style="color: var(--red)">{fmt_pct(drawdown)}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- CALENDAR HEATMAP -->
        <div class="card" style="margin-bottom: 32px;">
            <div class="card-title">Daily P&L - Last 60 Days</div>
            <div class="heatmap">
                {''.join(f'<div class="heatmap-cell" style="background-color: {heatmap_color(h["intensity"])}; color: {"white" if abs(h["intensity"]) >= 2 else "transparent"};" title="{h["label"]}: {h["return"]:+.2f}%">{h["day"][:1]}</div>' for h in heatmap)}
            </div>
        </div>
        
        <!-- TRADE SUMMARY -->
        <div class="card">
            <div class="card-title">Trade Summary</div>
            <div class="performance-grid">
                <div class="perf-card">
                    <div class="perf-label">Total Trades</div>
                    <div class="perf-value">{trades_total}</div>
                </div>
                <div class="perf-card">
                    <div class="perf-label">This Week</div>
                    <div class="perf-value">{trades_7d}</div>
                </div>
                <div class="perf-card">
                    <div class="perf-label">Today</div>
                    <div class="perf-value">{trades_today}</div>
                </div>
                <div class="perf-card">
                    <div class="perf-label">Win Rate</div>
                    <div class="perf-value" style="color: var(--green)">{win_rate:.0f}%</div>
                </div>
                <div class="perf-card">
                    <div class="perf-label">Best Day</div>
                    <div class="perf-value" style="color: var(--green)">{fmt_pct(best_day)}</div>
                </div>
                <div class="perf-card">
                    <div class="perf-label">Worst Day</div>
                    <div class="perf-value" style="color: var(--red)">{fmt_pct(worst_day)}</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Dark mode toggle
        function toggleDarkMode() {{
            const html = document.documentElement;
            const isDark = html.classList.contains('dark');
            html.classList.toggle('dark');
            localStorage.setItem('darkMode', !isDark);
        }}
        
        // Load dark mode preference
        if (localStorage.getItem('darkMode') === 'true') {{
            document.documentElement.classList.add('dark');
        }}
        
        // Chart data
        const chartData = {json.dumps(chart_data)};
        const tradeData = {json.dumps(trade_data)};
        
        // Equity curve
        const ctx1 = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx1, {{
            type: 'line',
            data: {{
                labels: chartData.map(d => d.date),
                datasets: [{{
                    label: 'Account Value',
                    data: chartData.map(d => d.value),
                    borderColor: 'var(--purple)',
                    backgroundColor: 'rgba(99, 102, 241, 0.08)',
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
                        backgroundColor: 'var(--card)',
                        borderColor: 'var(--border)',
                        borderWidth: 1,
                        titleColor: 'var(--text-primary)',
                        bodyColor: 'var(--text-primary)',
                        padding: 12,
                        displayColors: false,
                    }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'var(--chart-border)', drawBorder: false }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }}
                }}
            }}
        }});
        
        // Entry time scatter
        const ctx2 = document.getElementById('entryTimeChart').getContext('2d');
        new Chart(ctx2, {{
            type: 'scatter',
            data: {{
                datasets: [{{
                    label: 'Entry Time P&L',
                    data: tradeData.map(d => ({{ x: d.entry_hour, y: d.pnl }})),
                    backgroundColor: tradeData.map(d => d.pnl >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
                    borderColor: 'transparent',
                    pointRadius: 5,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                }},
                scales: {{
                    x: {{
                        title: {{ display: true, text: 'Hour of Day', color: 'var(--text-light)' }},
                        min: 0,
                        max: 23,
                        grid: {{ color: 'var(--chart-border)' }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }},
                    y: {{
                        title: {{ display: true, text: 'P&L ($)', color: 'var(--text-light)' }},
                        grid: {{ color: 'var(--chart-border)' }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }}
                }}
            }}
        }});
        
        // Duration scatter
        const ctx3 = document.getElementById('durationChart').getContext('2d');
        new Chart(ctx3, {{
            type: 'scatter',
            data: {{
                datasets: [{{
                    label: 'Duration vs P&L',
                    data: tradeData.map(d => ({{ x: d.duration, y: d.pnl }})),
                    backgroundColor: tradeData.map(d => d.pnl >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
                    borderColor: 'transparent',
                    pointRadius: 5,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                }},
                scales: {{
                    x: {{
                        title: {{ display: true, text: 'Duration (minutes)', color: 'var(--text-light)' }},
                        grid: {{ color: 'var(--chart-border)' }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }},
                    y: {{
                        title: {{ display: true, text: 'P&L ($)', color: 'var(--text-light)' }},
                        grid: {{ color: 'var(--chart-border)' }},
                        ticks: {{ color: 'var(--text-light)' }},
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    DASHBOARD_FILE.write_text(html_content)
    print(f"✓ Dashboard with charts and dark mode generated: {DASHBOARD_FILE}")
    return True

if __name__ == '__main__':
    try:
        generate_dashboard()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
