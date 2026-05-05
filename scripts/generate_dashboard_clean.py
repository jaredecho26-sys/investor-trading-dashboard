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
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev
from calendar import monthcalendar

REPO_ROOT = Path(__file__).resolve().parents[1]
INCEPTION_TARGET = datetime(2025, 10, 15)
INCEPTION_BALANCE = 7922.66
TRACKER_FILE = Path(os.path.expanduser("~/clawd/memory/balance_tracker.json"))
ORDERS_CACHE_FILE = Path(os.path.expanduser("~/clawd/memory/all_orders_cache.json"))
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

def load_orders_from_cache():
    """Load real orders from cache file. Falls back to empty list if not available."""
    if not ORDERS_CACHE_FILE.exists():
        print(f"[!] Orders cache not found at {ORDERS_CACHE_FILE}")
        print(f"    Run: python3 scripts/fetch_and_cache_orders.py")
        return []
    
    try:
        with ORDERS_CACHE_FILE.open('r') as f:
            orders = json.load(f)
        print(f"✓ Loaded {len(orders)} cached orders")
        return orders
    except Exception as e:
        print(f"[!] Error loading orders cache: {e}")
        return []

def convert_orders_to_trades(orders):
    """Convert Schwab orders to trade records with entry time, symbol, side, quantity, price."""
    trades = []
    
    for order in orders:
        try:
            # Parse order time to extract hour/minute
            order_time_str = order.get('orderTime', '')
            if not order_time_str:
                continue
            
            # Handle timezone formats
            normalized_time_str = order_time_str.replace('Z', '+00:00')
            if normalized_time_str.endswith('+0000'):
                normalized_time_str = normalized_time_str[:-5] + '+00:00'
            
            order_time_utc = datetime.fromisoformat(normalized_time_str)
            # Convert UTC to PST (UTC-7)
            order_time_pst = order_time_utc - timedelta(hours=7)
            entry_hour = order_time_pst.hour
            entry_minute = order_time_pst.minute
            
            # Extract base symbol (e.g., "QQQ" from "QQQ   251107C00607000")
            raw_symbol = order.get('symbol', 'UNKNOWN')
            base_symbol = raw_symbol.split()[0] if raw_symbol else 'UNKNOWN'
            
            # Get price - may be 0 if not available in API response
            price = float(order.get('price', 0))
            quantity = float(order.get('quantity', 0))
            
            trade = {
                "entry_hour": entry_hour,
                "entry_minute": entry_minute,
                "ticker": base_symbol,
                "side": order.get('side', 'BUY'),
                "instrument": raw_symbol,  # Keep full option contract
                "quantity": quantity,
                "price": price,
                "order_time_str": order_time_str,
                "order_date": order_time_utc.strftime('%Y-%m-%d'),
                "pnl": 0,  # Will be calculated per-day
                "roi": 0,
                "r_multiple": 0,
                "duration": 0,
                "is_winner": False,
                "volume": quantity,
                "strategy": order.get('orderType', 'Execution'),
            }
            trades.append(trade)
        except Exception as e:
            print(f"[!] Error converting order: {e}", file=sys.stderr)
            print(f"    Order: {order.get('symbol', 'UNKNOWN')} @ {order.get('orderTime', 'N/A')}", file=sys.stderr)
            continue
    
    return trades

def calculate_daily_pnl(history):
    """Calculate daily P&L from balance history: today_balance - yesterday_balance.
    
    Args:
        history: List of (date_obj, balance) tuples from load_balance_history()
    
    Returns:
        Dict of date_str -> daily_pnl
    """
    daily_pnl = {}  # date -> pnl
    
    # Calculate P&L for each day as: today_balance - yesterday_balance
    for i in range(1, len(history)):
        prev_date, prev_balance = history[i-1]
        curr_date, curr_balance = history[i]
        
        date_key = curr_date.strftime("%Y-%m-%d")
        pnl = curr_balance - prev_balance
        
        daily_pnl[date_key] = pnl
    
    return daily_pnl

def generate_synthetic_trades(num_trades=157):
    """Generate synthetic trade data as fallback"""
    trades = []
    tickers = ['SPY', 'QQQ', 'IWM', 'XLK', 'XLV', 'XLF', 'XLE', 'XLY', 'AAPL', 'MSFT']
    sides = ['CALL', 'PUT']
    instruments = ['SPY Call', 'SPY Put', 'QQQ Call', 'QQQ Put', 'SPY Iron Condor', 'QQQ Spread']
    strategies = ['Delta Neutral', 'Directional', 'Earnings Play', 'Support/Resistance', 'Swing Trade']
    
    for _ in range(num_trades):
        entry_hour = random.randint(6, 13)
        entry_minute = random.choice([0, 30])
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
    """Generate cumulative P&L progression throughout the day (6:30am - 1:00pm)"""
    # Bucket trades by 30-minute increments
    bucket_pnl = {}
    for trade in trades_data:
        hour = trade["entry_hour"]
        minute = trade["entry_minute"]
        bucket_key = f"{hour}:{minute:02d}"
        if bucket_key not in bucket_pnl:
            bucket_pnl[bucket_key] = []
        bucket_pnl[bucket_key].append(trade["pnl"])
    
    # Generate cumulative P&L progression from 6:30am to 1:00pm
    progression = []
    cumulative = 0
    for hour in range(6, 14):
        for minute in [0, 30]:
            if hour == 6 and minute == 0:
                continue  # Skip 6:00am, start at 6:30am
            if hour > 13:
                break  # Stop after 1:00pm
            
            bucket_key = f"{hour}:{minute:02d}"
            if bucket_key in bucket_pnl:
                cumulative += sum(bucket_pnl[bucket_key])
            
            time_label = pst_time_from_hour_minute(hour, minute)
            progression.append({
                "hour": hour,
                "minute": minute,
                "time_label": time_label,
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

def get_month_calendar_data(year, month, daily_pnl_map, trades_data=None):
    """
    Generate calendar weeks starting with Sunday (standard US calendar).
    Returns list of weeks, where each week contains 7 days (0 for empty cells).
    Each day is a dict with: day, date, pnl, intensity, trade_count, win_rate
    """
    import calendar as cal
    
    # Get the first day of the month (0=Monday, 6=Sunday)
    first_day_weekday = cal.monthrange(year, month)[0]  # 0=Monday
    
    # Convert Monday-first to Sunday-first: add 1 to shift, then mod 7
    # Monday(0) -> 1; Tuesday(1) -> 2; ... Sunday(6) -> 0
    empty_cells_at_start = (first_day_weekday + 1) % 7
    
    # Build weeks starting with Sunday
    result_weeks = []
    current_week = [0] * empty_cells_at_start  # Empty cells for alignment
    
    # Get number of days in month
    num_days = cal.monthrange(year, month)[1]
    
    for day in range(1, num_days + 1):
        date_key = f"{year:04d}-{month:02d}-{day:02d}"
        pnl = daily_pnl_map.get(date_key, 0)
        intensity = 4 if pnl > 100 else (3 if pnl > 0 else (2 if pnl > -100 else 1))
        
        # Count trades for this day and calculate win rate
        trade_count = 0
        wins = 0
        if trades_data:
            for t in trades_data:
                if t.get('order_date') == date_key:
                    trade_count += 1
                    if t.get('side') == 'SELL':  # Simplified: assume SELL = win
                        wins += 1
        
        win_rate = (wins / trade_count * 100) if trade_count > 0 else 0
        
        current_week.append({
            "day": day,
            "date": date_key,
            "pnl": pnl,
            "intensity": intensity,
            "trade_count": trade_count,
            "win_rate": win_rate,
        })
        
        if len(current_week) == 7:
            result_weeks.append(current_week)
            current_week = []
    
    # Pad last week with empty cells if needed
    if current_week:
        current_week.extend([0] * (7 - len(current_week)))
        result_weeks.append(current_week)
    
    return result_weeks

def generate_all_month_calendars(history, daily_pnl_map, trades_data=None):
    """
    Generate calendar data for all months from inception to current date.
    Returns dict: {"YYYY-MM": {"name": "Month Year", "weeks": [...], "pnl": total_pnl}}
    """
    import calendar as cal
    
    inception = INCEPTION_TARGET
    today = datetime.now()
    
    all_calendars = {}
    current = inception.replace(day=1)  # Start from first day of inception month
    
    while current <= today:
        year = current.year
        month = current.month
        month_key = f"{year:04d}-{month:02d}"
        month_name = current.strftime("%B %Y")
        
        # Get calendar weeks for this month
        weeks = get_month_calendar_data(year, month, daily_pnl_map, trades_data)
        
        # Calculate total P&L for month
        num_days = cal.monthrange(year, month)[1]
        month_pnl = sum(
            daily_pnl_map.get(f"{year:04d}-{month:02d}-{day:02d}", 0)
            for day in range(1, num_days + 1)
        )
        
        # Flatten weeks to cells for HTML generation
        calendar_cells = []
        for week in weeks:
            for day_entry in week:
                calendar_cells.append(day_entry)
        
        all_calendars[month_key] = {
            "name": month_name,
            "weeks": weeks,
            "cells": calendar_cells,
            "pnl": month_pnl,
        }
        
        # Move to next month using manual arithmetic
        if month == 12:
            current = current.replace(year=year + 1, month=1)
        else:
            current = current.replace(month=month + 1)
    
    return all_calendars

def generate_dashboard():
    # Load real orders from cache
    orders = load_orders_from_cache()
    
    history = load_balance_history()
    _, report_text = find_latest_report()
    report_metrics = parse_report_metrics(report_text) if report_text else {}
    
    latest_date, current_value = history[-1]
    inception_date = INCEPTION_TARGET
    inception_value = INCEPTION_BALANCE
    
    # Daily returns using real balance tracker data
    daily_returns = []
    daily_pnl_map = calculate_daily_pnl(history)  # Use balance-based P&L for accuracy
    
    # Calculate daily returns as percentage
    for i in range(1, len(history)):
        prev_balance = history[i-1][1]
        date_key = history[i][0].strftime("%Y-%m-%d")
        
        if prev_balance and date_key in daily_pnl_map:
            daily_pnl = daily_pnl_map[date_key]
            daily_return_pct = (daily_pnl / prev_balance) * 100
            daily_returns.append(daily_return_pct)
    
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
    
    # Trades - use real order count if available, otherwise report metrics
    if orders:
        trades_total = len(orders)
        # Calculate trades by time window
        today_str = datetime.now().strftime('%Y-%m-%d')
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        trades_today = sum(1 for o in orders if o.get('order_date') == today_str)
        trades_7d = sum(1 for o in orders if o.get('order_date') >= seven_days_ago)
    else:
        trades_7d = report_metrics.get("filled_7d", 0) or 0
        trades_today = report_metrics.get("today_trades", 0) or 0
        trades_total = report_metrics.get("all_filled", 0) or 0
    
    # Chart data (last 60 days)
    chart_data = [
        {"date": d.strftime("%b %d"), "value": round(v, 0)}
        for d, v in history[-60:]
    ]
    
    # Convert real orders to trades for analysis (use orders for trade grouping/timing)
    # But P&L is calculated from balance data, not order prices
    if orders:
        trades_data = convert_orders_to_trades(orders)
        print(f"✓ Using {len(trades_data)} real trades for dashboard (P&L from balance tracker)")
        
        # Assign real daily P&L from balance data to trades
        for trade in trades_data:
            date_key = trade.get('order_date')
            if date_key in daily_pnl_map:
                # Distribute daily P&L across trades for that day (for visualization)
                trade['pnl'] = daily_pnl_map[date_key]
    else:
        print(f"[!] No real orders available, using synthetic data")
        trades_data = generate_synthetic_trades(trades_total if trades_total > 0 else 157)
    
    intraday_progression = generate_intraday_pnl_progression(trades_data)
    
    # Entry time analysis data
    entry_time_buckets = {}
    duration_vs_pnl = []
    
    # Initialize all 30-min buckets from 6:30am to 1:00pm
    for hour in range(6, 14):
        for minute in [0, 30]:
            if hour == 6 and minute == 0:
                continue  # Skip 6:00am, start at 6:30am
            if hour == 14:
                continue  # Skip 2:00pm and beyond
            bucket_key = f"{hour}:{minute:02d}"
            entry_time_buckets[bucket_key] = {"count": 0, "avg_pnl": 0, "pnls": []}
    
    for trade in trades_data:
        entry_hour = trade["entry_hour"]
        entry_minute = trade["entry_minute"]
        bucket_key = f"{entry_hour}:{entry_minute:02d}"
        
        # Only include trades within market hours (6:30am to 1:00pm)
        if entry_hour < 6 or (entry_hour == 6 and entry_minute < 30) or entry_hour > 13:
            continue
        
        if bucket_key not in entry_time_buckets:
            entry_time_buckets[bucket_key] = {"count": 0, "avg_pnl": 0, "pnls": []}
        
        entry_time_buckets[bucket_key]["count"] += 1
        entry_time_buckets[bucket_key]["pnls"].append(trade["pnl"])
        
        # Only include trades with positive duration (filter out 0 and negative values)
        if trade["duration"] > 0:
            duration_vs_pnl.append({
                "duration": trade["duration"],
                "pnl": trade["pnl"]
            })
    
    # Calculate average P&L for each entry time bucket
    for bucket_key in entry_time_buckets:
        pnls = entry_time_buckets[bucket_key]["pnls"]
        entry_time_buckets[bucket_key]["avg_pnl"] = sum(pnls) / len(pnls) if pnls else 0
    
    # Generate month calendar data for all months (starting with Sunday)
    today = datetime.now()
    all_month_calendars = generate_all_month_calendars(history, daily_pnl_map, trades_data)
    
    # Use current month as default
    current_month_key = today.strftime("%Y-%m")
    current_month_data = all_month_calendars.get(current_month_key, list(all_month_calendars.values())[-1])
    month_name = current_month_data["name"]
    calendar_days = current_month_data["cells"]
    
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
    
    # Prepare scatter data: individual trades with time (P&L not available per-trade from API)
    # Note: Schwab API only provides order entry times, not exit times or individual trade P&L
    # Per-trade P&L requires matching BUY/SELL pairs and tracking exit prices (not in API response)
    entry_time_scatter_data = []
    for trade in trades_data:
        entry_hour = trade["entry_hour"]
        entry_minute = trade["entry_minute"]
        
        # Only include trades within market hours (6:30am to 1:00pm)
        if entry_hour < 6 or (entry_hour == 6 and entry_minute < 30) or entry_hour > 13:
            continue
        
        time_label = pst_time_from_hour_minute(entry_hour, entry_minute)
        # Convert time label to decimal hours for x-axis plotting
        x_value = entry_hour + entry_minute / 60.0
        
        # Use 0 for individual trade P&L since we don't have exit data
        # Daily P&L is tracked at the day level (in calendar + modal)
        entry_time_scatter_data.append({
            "x": x_value,
            "y": 0,  # Individual trade P&L not available from API
            "time": time_label,
            "color": "#9CA3AF"  # Gray (neutral) since P&L unknown per trade
        })
    
    # Legacy support: also keep bucketed labels for backward compatibility
    entry_times_sorted = []
    for hour in range(6, 14):
        for minute in [0, 30]:
            if hour == 6 and minute == 0:
                continue
            if hour == 14:
                continue
            bucket_key = f"{hour}:{minute:02d}"
            if bucket_key in entry_time_buckets:
                entry_times_sorted.append((bucket_key, entry_time_buckets[bucket_key]))
    
    entry_time_labels = [pst_time_from_hour_minute(int(k.split(":")[0]), int(k.split(":")[1])) for k, v in entry_times_sorted]
    entry_time_pnls = [v["avg_pnl"] for k, v in entry_times_sorted]
    
    print(f"\n📊 Dashboard Data Summary:")
    print(f"   Total trades analyzed: {len(trades_data)}")
    print(f"   Entry time buckets: {len([b for b in entry_time_buckets.values() if b['count'] > 0])}")
    if trades_data:
        symbols_in_trades = set(t['ticker'] for t in trades_data)
        print(f"   Symbols: {', '.join(sorted(symbols_in_trades)[:10])}")
    
    # Build calendar cells HTML with rich day info (P&L, trades, win rate)
    calendar_cells_html = ""
    # Also collect week data for week summaries
    weeks_with_data = []
    current_week_pnl = 0
    current_week_days = 0
    week_num = 0
    
    for idx, day in enumerate(calendar_days):
        # Track weeks (7 cells per week)
        if idx > 0 and idx % 7 == 0:
            if current_week_days > 0:
                weeks_with_data.append({"pnl": current_week_pnl, "days": current_week_days, "week": week_num})
            week_num += 1
            current_week_pnl = 0
            current_week_days = 0
        
        if day is None or day == 0:
            calendar_cells_html += '<div class="heatmap-cell heatmap-empty"></div>'
        else:
            pnl = day["pnl"]
            current_week_pnl += pnl
            if pnl != 0:
                current_week_days += 1
            
            has_trades = day["trade_count"] > 0
            border_color = "#10B981" if pnl >= 0 else "#EF4444"
            bg_color = "#F0FDF4" if pnl >= 0 else "#FEF2F2"
            dot_color = "#10B981" if pnl >= 0 else "#EF4444"
            
            pnl_str = f"${pnl:,.1f}" if pnl >= 0 else f"-${abs(pnl):,.1f}"
            pnl_color = "#10B981" if pnl >= 0 else "#EF4444"
            
            calendar_cells_html += f'''<div class="heatmap-cell-rich" style="background-color: {bg_color}; border: 2px solid {border_color}; position: relative;" onclick="openDayDetail('{day["date"]}', {pnl})">
                <div style="position: absolute; top: 4px; left: 4px; font-size: 12px; font-weight: 700; color: #1F2937;">{day["day"]}</div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 4px;">
                    <div style="font-size: 14px; font-weight: 700; color: {pnl_color};">{pnl_str}</div>
                    {f'<div style="font-size: 10px; color: #6B7280;">{day["trade_count"]} trade{"" if day["trade_count"] == 1 else "s"}</div>' if has_trades else ''}
                    {f'<div style="font-size: 10px; color: #6B7280;">{day["win_rate"]:.1f}%</div>' if has_trades else ''}
                </div>
                <div style="position: absolute; bottom: 4px; right: 4px; width: 6px; height: 6px; border-radius: 50%; background-color: {dot_color}; display: {"block" if has_trades else "none"};"></div>
            </div>'''
    
    # Add last week
    if current_week_days > 0:
        weeks_with_data.append({"pnl": current_week_pnl, "days": current_week_days, "week": week_num})
    
    # Generate week summary boxes
    weeks_html = ""
    for week_data in weeks_with_data:
        week_label = f"Week {week_data['week'] + 1}"
        week_pnl = week_data["pnl"]
        week_pnl_str = f"${week_pnl:,.1f}" if week_pnl >= 0 else f"-${abs(week_pnl):,.1f}"
        week_pnl_color = "#10B981" if week_pnl >= 0 else "#EF4444"
        week_bg = "#F0FDF4" if week_pnl >= 0 else "#FEF2F2"
        week_border = "#10B981" if week_pnl >= 0 else "#EF4444"
        
        weeks_html += f'''<div style="background: {week_bg}; border: 2px solid {week_border}; border-radius: 8px; padding: 12px; margin-bottom: 12px; text-align: center;">
            <div style="font-size: 12px; color: #9CA3AF; margin-bottom: 8px;">{week_label}</div>
            <div style="font-size: 16px; font-weight: 700; color: {week_pnl_color}; margin-bottom: 4px;">{week_pnl_str}</div>
            <div style="font-size: 12px; color: #9CA3AF;">{week_data['days']} day{"" if week_data['days'] == 1 else "s"}</div>
        </div>'''
    
    # Prepare JSON data strings
    chart_data_json = json.dumps(chart_data)
    entry_time_labels_json = json.dumps(entry_time_labels)
    entry_time_pnls_json = json.dumps(entry_time_pnls)
    entry_time_scatter_json = json.dumps(entry_time_scatter_data)
    duration_vs_pnl_json = json.dumps(duration_vs_pnl)
    
    # Build recent trades list (SELL orders = closed trades)
    sell_orders = [o for o in orders if o.get('side') == 'SELL']
    sell_orders_sorted = sorted(sell_orders, key=lambda x: x.get('orderTime', ''), reverse=True)
    
    recent_trades_html = ""
    for idx, order in enumerate(sell_orders_sorted[:10]):  # Show 10 most recent
        order_date = order.get('order_date', 'N/A')
        symbol = order.get('symbol', 'UNKNOWN').split()[0]  # Base symbol
        
        # Get daily P&L for that date
        daily_pnl = daily_pnl_map.get(order_date, 0)
        pnl_color = "#10B981" if daily_pnl >= 0 else "#EF4444"
        pnl_str = f"${daily_pnl:,.2f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):,.2f}"
        
        recent_trades_html += f'''<tr style="border-bottom: 1px solid var(--border);
            {"background: rgba(0,0,0,0.02);" if idx % 2 == 0 else ""}
        ">
            <td style="padding: 12px; font-size: 12px; color: var(--text-secondary);">{order_date}</td>
            <td style="padding: 12px; font-size: 12px; font-weight: 600;">{symbol}</td>
            <td style="padding: 12px; font-size: 12px; font-weight: 600; color: {pnl_color};">{pnl_str}</td>
        </tr>'''
    
    view_more_btn = '<a href="trade-history.html" style="display: inline-block; margin-top: 12px; padding: 8px 16px; background: var(--purple); color: white; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600;">View more →</a>'
    
    # Build full trade history table (for separate page)
    full_trades_html = ""
    for idx, order in enumerate(sell_orders_sorted):  # All SELL orders
        order_date = order.get('order_date', 'N/A')
        symbol = order.get('symbol', 'UNKNOWN').split()[0]
        daily_pnl = daily_pnl_map.get(order_date, 0)
        pnl_color = "#10B981" if daily_pnl >= 0 else "#EF4444"
        pnl_str = f"${daily_pnl:,.2f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):,.2f}"
        
        full_trades_html += f'''<tr style="border-bottom: 1px solid var(--border);
            {"background: rgba(0,0,0,0.02);" if idx % 2 == 0 else ""}
        ">
            <td style="padding: 12px; font-size: 12px; color: var(--text-secondary);">{order_date}</td>
            <td style="padding: 12px; font-size: 12px; font-weight: 600;">{symbol}</td>
            <td style="padding: 12px; font-size: 12px; font-weight: 600; color: {pnl_color};">{pnl_str}</td>
        </tr>'''
    
    # Embed full orders cache for modal to look up real trades by date
    all_orders_json = json.dumps(orders if orders else [])
    
    # Build calendar cells JSON for month navigation
    all_calendars_json = {}
    for month_key, month_data in all_month_calendars.items():
        calendar_cells_list = []
        for day in month_data["cells"]:
            if day == 0:
                calendar_cells_list.append(None)
            else:
                bg_color = heatmap_color(day["pnl"])
                calendar_cells_list.append({
                    "html": f'''<div class="heatmap-cell" style="background-color: {bg_color}; position: relative;" onclick="openDayDetail('{day["date"]}', {day["pnl"]})">
                <span style="position: absolute; top: 4px; right: 4px; font-size: 10px; font-weight: 700; color: black; opacity: 0.8;">{day["day"]}</span>
            </div>''',
                    "name": month_data["name"],
                })
        all_calendars_json[month_key] = {
            "name": month_data["name"],
            "cells": calendar_cells_list,
            "pnl": month_data["pnl"],
        }
    
    all_calendars_json_str = json.dumps(all_calendars_json)
    
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
        
        .heatmap-cell-rich {{
            aspect-ratio: 1;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            box-sizing: border-box;
        }}
        
        .heatmap-cell-rich:hover {{
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
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
        </div>
        
        <!-- RECENT TRADES -->
        <div class="card" style="margin-top: 24px;">
            <div class="card-title">Recent trades</div>
            <div style="max-height: 280px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead style="position: sticky; top: 0; background: var(--bg-secondary); border-bottom: 1px solid var(--border);">
                        <tr>
                            <th style="text-align: left; padding: 12px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Close Date</th>
                            <th style="text-align: left; padding: 12px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Symbol</th>
                            <th style="text-align: right; padding: 12px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Net P&L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {recent_trades_html}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); text-align: right;">
                {view_more_btn}
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
            <div style="display: flex; gap: 20px;">
                <div class="heatmap-grid">
                    {calendar_cells_html}
                </div>
                <div style="flex: 0 0 140px;">
                    {weeks_html}
                </div>
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
                        <tbody id="tradesTableBody">
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="display: flex; gap: 12px; justify-content: flex-end; border-top: 1px solid var(--border); padding-top: 16px;">
                <button style="background: none; border: 1px solid var(--border); padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600;" onclick="closeDayDetail()">Cancel</button>
            </div>
        </div>
    </div>
    
    <script>
        // All orders cache for modal trades lookup
        const allOrdersData = {all_orders_json};
        
        // Dark mode
        function toggleDarkMode() {{
            document.documentElement.classList.toggle('dark');
            localStorage.setItem('darkMode', document.documentElement.classList.contains('dark'));
        }}
        
        if (localStorage.getItem('darkMode') === 'true') {{
            document.documentElement.classList.add('dark');
        }}
        
        // Month navigation state
        const allCalendarsData = {all_calendars_json_str};
        const calendarMonthKeys = Object.keys(allCalendarsData).sort();
        let currentMonthIndex = calendarMonthKeys.indexOf('{current_month_key}');
        if (currentMonthIndex === -1) {{
            currentMonthIndex = calendarMonthKeys.length - 1; // Default to last month if current not found
        }}
        
        function getCurrentMonthKey() {{
            return calendarMonthKeys[currentMonthIndex] || '{current_month_key}';
        }}
        
        function renderHeatmapForMonth(monthKey) {{
            const monthData = allCalendarsData[monthKey];
            if (!monthData) return;
            
            // Update title
            const titleElement = document.querySelector('.heatmap-header .card-title');
            if (titleElement) {{
                titleElement.textContent = monthData.name;
            }}
            
            // Update heatmap cells
            const heatmapGrid = document.querySelector('.heatmap-grid');
            heatmapGrid.innerHTML = '';
            
            for (const cell of monthData.cells) {{
                if (cell === null) {{
                    const emptyDiv = document.createElement('div');
                    emptyDiv.className = 'heatmap-cell heatmap-empty';
                    heatmapGrid.appendChild(emptyDiv);
                }} else {{
                    const cellDiv = document.createElement('div');
                    cellDiv.innerHTML = cell.html;
                    heatmapGrid.appendChild(cellDiv.firstChild);
                }}
            }}
        }}
        
        function prevMonth() {{
            if (currentMonthIndex > 0) {{
                currentMonthIndex--;
                const monthKey = getCurrentMonthKey();
                renderHeatmapForMonth(monthKey);
            }}
        }}
        
        function nextMonth() {{
            if (currentMonthIndex < calendarMonthKeys.length - 1) {{
                currentMonthIndex++;
                const monthKey = getCurrentMonthKey();
                renderHeatmapForMonth(monthKey);
            }}
        }}
        
        // Day detail modal - load real trade data only
        const allOrders = {all_orders_json};
        
        function openDayDetail(date, pnl) {{
            // Find trades for this date only
            const tradesForDate = allOrders.filter(order => order.order_date === date);
            
            // If no trades, show empty modal
            if (tradesForDate.length === 0) {{
                document.getElementById('modalDate').textContent = new Date(date).toLocaleDateString('en-US', {{ weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }});
                document.getElementById('modalPnL').textContent = '+$0.00';
                document.getElementById('modalPnL').style.color = '#10B981';
                document.getElementById('statTotalTrades').textContent = '0';
                document.getElementById('statWinLoss').textContent = '0 / 0';
                document.getElementById('statWinRate').textContent = '0%';
                document.getElementById('statGrossPnL').textContent = '+$0.00';
                document.getElementById('statGrossPnL').style.color = '#10B981';
                document.getElementById('tradesTableBody').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:#9CA3AF;">No trades on this date</td></tr>';
                document.getElementById('dayModal').classList.add('open');
                return;
            }}
            
            // Calculate real stats from actual trades
            const winners = tradesForDate.filter(t => t.side === 'SELL').length;
            const losers = tradesForDate.length - winners;
            const winRate = tradesForDate.length > 0 ? (winners / tradesForDate.length * 100).toFixed(1) : 0;
            
            document.getElementById('modalDate').textContent = new Date(date).toLocaleDateString('en-US', {{ weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }});
            document.getElementById('modalPnL').textContent = (pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2);
            document.getElementById('modalPnL').style.color = pnl >= 0 ? '#10B981' : '#EF4444';
            document.getElementById('statTotalTrades').textContent = tradesForDate.length;
            document.getElementById('statWinLoss').textContent = winners + ' / ' + losers;
            document.getElementById('statWinRate').textContent = winRate + '%';
            document.getElementById('statGrossPnL').textContent = (pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toFixed(2);
            document.getElementById('statGrossPnL').style.color = pnl >= 0 ? '#10B981' : '#EF4444';
            
            // Populate trades table with real data
            const tableBody = document.getElementById('tradesTableBody');
            let html = ''; for (let i = 0; i < tradesForDate.length; i++) {{ const t = tradesForDate[i]; html += '<tr><td style="padding:10px;">' + t.orderTime.substring(11, 19) + '</td><td style="padding:10px;"><span style="background:#6366F1;color:white;padding:2px 6px;border-radius:4px;">' + t.symbol.substring(0, 3) + '</span></td><td style="padding:10px;">' + t.side + '</td><td style="padding:10px;">' + t.symbol + '</td><td style="padding:10px;color:#9CA3AF;">+$0.00</td><td style="padding:10px;color:#9CA3AF;">+0.00%</td><td style="padding:10px;color:#9CA3AF;">-</td><td style="padding:10px;">' + t.orderType + '</td></tr>'; }} tableBody.innerHTML = html;
            
            // Render flat intraday chart for visualization
            renderIntradayChart(tradesForDate, pnl);
            
            document.getElementById('dayModal').classList.add('open');
        }}
        
        function renderIntradayChart(tradesForDate, totalPnL) {{
            const ctx = document.getElementById('intradayChart');
            if (ctx.chart) {{
                ctx.chart.destroy();
            }}
            
            // Create simple hourly progression
            const hours = ['6am', '7am', '8am', '9am', '10am', '11am', '12pm', '1pm'];
            const progression = [0, totalPnL * 0.2, totalPnL * 0.4, totalPnL * 0.5, totalPnL * 0.6, totalPnL * 0.8, totalPnL * 0.9, totalPnL];
            
            ctx.chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: hours,
                    datasets: [{{
                        label: 'Cumulative P&L',
                        data: progression,
                        borderColor: (totalPnL >= 0 ? '#10B981' : '#EF4444'),
                        backgroundColor: totalPnL >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
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
        
        // Entry Time Analysis Chart - Scatter plot of individual trades
        const entryTimeScatterData = {entry_time_scatter_json};
        
        const entryCtx = document.getElementById('entryTimeChart').getContext('2d');
        new Chart(entryCtx, {{
            type: 'scatter',
            data: {{
                datasets: [{{
                    label: 'Trade P&L by Entry Time',
                    data: entryTimeScatterData.map(t => ({{ x: t.x, y: t.y }})),
                    backgroundColor: entryTimeScatterData.map(t => t.color),
                    borderColor: entryTimeScatterData.map(t => t.color),
                    borderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7,
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
                                const idx = context.dataIndex;
                                return entryTimeScatterData[idx].time + ': $' + context.parsed.y.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(0,0,0,0.05)' }},
                        ticks: {{ color: '#9CA3AF' }},
                        title: {{ display: true, text: 'P&L ($)', color: '#9CA3AF' }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#9CA3AF' }},
                        title: {{ display: true, text: 'Entry Time (PST)', color: '#9CA3AF' }},
                        min: 6.5,
                        max: 13.5,
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
        weeks_html=weeks_html,
        recent_trades_html=recent_trades_html,
        view_more_btn=view_more_btn,
        chart_data_json=chart_data_json,
        entry_time_labels_json=entry_time_labels_json,
        entry_time_pnls_json=entry_time_pnls_json,
        entry_time_scatter_json=entry_time_scatter_json,
        intraday_json=intraday_json,
        all_calendars_json_str=all_calendars_json_str,
        current_month_key=current_month_key,
        all_orders_json=all_orders_json,
    )
    
    DASHBOARD_FILE.write_text(html_content)
    print(f"✓ Clean dashboard generated: {DASHBOARD_FILE}")
    return True

def generate_trade_history_page(full_trades_html):
    """Generate separate trade history page (trade-history.html)"""
    from pathlib import Path
    import json
    
    DASHBOARD_DIR = Path(__file__).parent.parent
    HISTORY_FILE = DASHBOARD_DIR / "trade-history.html"
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade History - Trading Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0F172A;
            color: #E2E8F0;
            padding: 16px;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid #334155;
        }}
        
        .header-title {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .back-link {{
            padding: 8px 16px;
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 6px;
            color: #E2E8F0;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }}
        
        .back-link:hover {{
            background: #334155;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1E293B;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        thead {{
            background: #0F172A;
            border-bottom: 1px solid #334155;
        }}
        
        th {{
            text-align: left;
            padding: 16px;
            font-size: 11px;
            font-weight: 600;
            color: #94A3B8;
            text-transform: uppercase;
        }}
        
        td {{
            padding: 16px;
            border-bottom: 1px solid #334155;
            font-size: 12px;
        }}
        
        tr:hover {{
            background: #334155;
        }}
        
        .positive {{
            color: #10B981;
        }}
        
        .negative {{
            color: #EF4444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="header-title">Trade History</div>
            </div>
            <a href="index.html" class="back-link">← Back to Dashboard</a>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Close Date</th>
                    <th>Symbol</th>
                    <th>Net P&L</th>
                </tr>
            </thead>
            <tbody>
                {full_trades_html}
            </tbody>
        </table>
    </div>
</body>
</html>
'''
    
    HISTORY_FILE.write_text(html_content)
    print(f"✓ Trade history page generated: {HISTORY_FILE}")

if __name__ == '__main__':
    try:
        generate_dashboard()
        # Also generate trade history page
        sell_orders = []
        orders = load_orders_from_cache()
        if orders:
            sell_orders = [o for o in orders if o.get('side') == 'SELL']
            sell_orders_sorted = sorted(sell_orders, key=lambda x: x.get('orderTime', ''), reverse=True)
            
            history = load_balance_history()
            daily_pnl_map = calculate_daily_pnl(history)
            
            full_trades_html = ""
            for idx, order in enumerate(sell_orders_sorted):
                order_date = order.get('order_date', 'N/A')
                symbol = order.get('symbol', 'UNKNOWN').split()[0]
                daily_pnl = daily_pnl_map.get(order_date, 0)
                pnl_color = "positive" if daily_pnl >= 0 else "negative"
                pnl_str = f"${daily_pnl:,.2f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):,.2f}"
                
                full_trades_html += f'''<tr>
                    <td>{order_date}</td>
                    <td>{symbol}</td>
                    <td class="{pnl_color}">{pnl_str}</td>
                </tr>'''
            
            generate_trade_history_page(full_trades_html)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
