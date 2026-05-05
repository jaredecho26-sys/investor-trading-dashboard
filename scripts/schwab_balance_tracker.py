#!/usr/bin/env python3
"""
Track daily balance snapshots for rolling 30-day and YTD (Jan 1, 2026) calculations
Tracks back to 10/15/2025
"""

import json
import os
from datetime import datetime, timedelta

TRACKER_FILE = os.path.expanduser("~/clawd/memory/balance_tracker.json")

def ensure_tracker():
    """Create tracker if it doesn't exist"""
    if not os.path.exists(TRACKER_FILE):
        os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
        with open(TRACKER_FILE, 'w') as f:
            json.dump({}, f, indent=2)

def save_daily_balance(balance):
    """Save today's closing balance"""
    ensure_tracker()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    with open(TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    # Always update with latest balance for today
    tracker[today] = balance
    with open(TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2)

def get_balance_on_date(target_date):
    """Get the balance on a specific date (YYYY-MM-DD string or datetime object)"""
    ensure_tracker()
    
    if isinstance(target_date, datetime):
        target_date = target_date.strftime('%Y-%m-%d')
    
    with open(TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    # If exact date exists, return it
    if target_date in tracker:
        return tracker[target_date]
    
    # Otherwise, find the most recent balance on or before that date
    for date in sorted(tracker.keys(), reverse=True):
        if date <= target_date:
            return tracker[date]
    
    return None

def get_rolling_30day_change():
    """Calculate % change and $ change over last 30 rolling days"""
    ensure_tracker()
    
    today = datetime.now()
    thirty_days_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    with open(TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    current = tracker.get(today_str)
    baseline = get_balance_on_date(thirty_days_ago)
    
    if not current:
        # No current balance
        return None, None, True
    
    if not baseline:
        # Not enough data (less than 30 days of tracking)
        # Return change from earliest available date
        earliest_date = sorted(tracker.keys())[0]
        baseline = tracker[earliest_date]
        change_usd = current - baseline
        change_pct = (change_usd / baseline * 100) if baseline > 0 else 0
        return change_pct, change_usd, False
    
    change_usd = current - baseline
    change_pct = (change_usd / baseline * 100) if baseline > 0 else 0
    
    return change_pct, change_usd, False

def get_ytd_change():
    """Calculate change from Jan 1, 2026 to today"""
    ensure_tracker()
    
    today = datetime.now().strftime('%Y-%m-%d')
    jan1_2026 = '2026-01-01'
    
    with open(TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    current = tracker.get(today)
    
    # Try to get balance on Jan 1, 2026 specifically
    baseline = tracker.get(jan1_2026)
    
    # If not available, find the earliest 2026 balance
    if not baseline:
        for date in sorted(tracker.keys()):
            if date.startswith('2026-'):
                baseline = tracker[date]
                break
    
    if not current or not baseline:
        # Not enough data yet
        return None, None, baseline is None
    
    change_usd = current - baseline
    change_pct = (change_usd / baseline * 100) if baseline > 0 else 0
    
    return change_pct, change_usd, False

def get_earliest_date():
    """Get earliest date in tracker"""
    ensure_tracker()
    
    with open(TRACKER_FILE, 'r') as f:
        tracker = json.load(f)
    
    if not tracker:
        return None
    
    return sorted(tracker.keys())[0]

if __name__ == '__main__':
    # Test
    ensure_tracker()
    save_daily_balance(30628.55)
    
    rolling_pct, rolling_usd, no_30day_data = get_rolling_30day_change()
    ytd_pct, ytd_usd, no_ytd_data = get_ytd_change()
    
    print(f"Rolling 30-day: {rolling_pct:+.2f}% (${rolling_usd:+,.2f})" if not no_30day_data else "Rolling 30-day: Not enough data")
    print(f"YTD (Jan 1, 2026): {ytd_pct:+.2f}% (${ytd_usd:+,.2f})" if not no_ytd_data else "YTD: Not enough data")
    print(f"Earliest date in tracker: {get_earliest_date()}")
