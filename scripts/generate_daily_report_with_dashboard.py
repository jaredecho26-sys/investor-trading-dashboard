#!/usr/bin/env python3
"""
Generate daily trading report + dashboard + shareable URL
Complete investor update package - runs daily at 1:05 PM
"""

import json
import urllib.request
import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = REPO_ROOT / "reports"
INCEPTION_DATE = datetime(2025, 11, 1, tzinfo=timezone.utc).astimezone()

sys.path.insert(0, str(SCRIPT_DIR))
from schwab_token_utils import get_fresh_access_token
from schwab_balance_tracker import save_daily_balance

def get_balance_metric(days_back=None):
    """Get balance change metric from tracker"""
    tracker_file = os.path.expanduser("~/clawd/memory/balance_tracker.json")
    
    try:
        with open(tracker_file, 'r') as f:
            balances = json.load(f)
    except:
        return None, None
    
    today = datetime.now().strftime('%Y-%m-%d')
    today_balance = balances.get(today)
    
    if not today_balance:
        return None, None
    
    if days_back is None:
        baseline_date = '2026-01-01'
    elif days_back == 30:
        baseline_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    else:
        baseline_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    baseline_balance = balances.get(baseline_date)
    
    if not baseline_balance:
        for date in sorted(balances.keys(), reverse=True):
            if date <= baseline_date:
                baseline_balance = balances[date]
                break
    
    if not baseline_balance:
        return None, None
    
    change_usd = today_balance - baseline_balance
    change_pct = (change_usd / baseline_balance * 100) if baseline_balance > 0 else 0
    
    return change_pct, change_usd

def generate_report(include_dashboard_url=True):
    """Generate trading report with optional dashboard URL"""
    
    try:
        access_token = get_fresh_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        # Get account data
        req = urllib.request.Request("https://api.schwabapi.com/trader/v1/accounts", headers=headers)
        with urllib.request.urlopen(req) as response:
            accounts = json.loads(response.read().decode('utf-8'))
        
        account = accounts[0]['securitiesAccount']
        current_balances = account.get('currentBalances', {})
        initial_balances = account.get('initialBalances', {})
        
        current_value = current_balances.get('liquidationValue', 0)
        initial_value = initial_balances.get('liquidationValue', 0)
        daily_pnl = current_value - initial_value
        daily_pnl_pct = (daily_pnl / initial_value * 100) if initial_value > 0 else 0
        
        # Save today's closing balance to tracker (for dashboard updates)
        print(f"[*] Saving balance snapshot: ${current_value:,.2f}")
        save_daily_balance(current_value)
        
        # Get rolling 30-day and YTD metrics
        rolling_30_pct, rolling_30_usd = get_balance_metric(days_back=30)
        ytd_pct, ytd_usd = get_balance_metric(days_back=None)
        
        # Get orders
        end_date = datetime.now(timezone.utc).astimezone()
        start_date = end_date - timedelta(days=7)
        
        url = f"https://api.schwabapi.com/trader/v1/orders?fromEnteredTime={start_date.isoformat()}&toEnteredTime={end_date.isoformat()}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            orders = json.loads(response.read().decode('utf-8'))
        
        filled_count = len([o for o in orders if o.get('status') == 'FILLED'])
        today = datetime.now().strftime('%Y-%m-%d')
        today_trades = len([o for o in orders if o.get('enteredTime', '').startswith(today) and o.get('status') == 'FILLED'])
        
        # Get all-time trades
        all_start = INCEPTION_DATE
        all_url = f"https://api.schwabapi.com/trader/v1/orders?fromEnteredTime={all_start.isoformat()}&toEnteredTime={end_date.isoformat()}&maxResults=500"
        req = urllib.request.Request(all_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            all_orders = json.loads(response.read().decode('utf-8'))
        
        all_filled = len([o for o in all_orders if o.get('status') == 'FILLED'])
        
        # Format metrics
        rolling_30_str = f"{rolling_30_pct:+.2f}% (${rolling_30_usd:+,.2f})" if rolling_30_pct is not None else "(calculating)"
        ytd_str = f"{ytd_pct:+.2f}% (${ytd_usd:+,.2f})" if ytd_pct is not None else "(calculating)"
        
        # Build report
        report = f"""📊 1:05 PM DAILY TRADING REPORT
{datetime.now().strftime('%A, %B %d, %Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **DAILY P&L: {daily_pnl:+,.2f} ({daily_pnl_pct:+.2f}%)**

Portfolio Snapshot:
  • Current Value: ${current_value:,.2f}
  • Prior Close: ${initial_value:,.2f}
  • Cash Position: ${current_balances.get('cashBalance', 0):,.2f}

📈 TRADES TAKEN:
  • Last 7 Days: {filled_count} filled orders
  • Today: {today_trades} trades
  • Since 11/01/2025: {all_filled} trades

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 PERFORMANCE METRICS:
  • % Change (Today): {daily_pnl_pct:+.2f}%
  • % Change (Last 30 Days): {rolling_30_str}
  • YTD Change (Jan 1, 2026): {ytd_str}

⏰ Generated: {datetime.now().strftime('%I:%M %p PT')}
✅ Automation Status: WORKING

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 **INTERACTIVE DASHBOARD:**
   https://jaredpope-trading-dashboard.loca.lt

   📊 View live charts, metrics & performance
   🔄 Updates automatically daily at 1:05 PM PT
   📱 Mobile-friendly, works on any device
   🌐 Share this link with investors
"""
        
        # Save report first so dashboard generation picks up the latest daily note
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        report_file = REPORT_DIR / f"{datetime.now().strftime('%Y-%m-%d')}-trading-report.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Generate cached dashboard after the new report and balance snapshot are written
        print("[*] Generating HTML dashboard with fresh data...")
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / 'generate_cached_dashboard.py')],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.stdout:
                print(result.stdout)
            if result.returncode != 0:
                print(f"[!] Dashboard generation warning: {result.stderr}")
        except Exception as e:
            print(f"[!] Error generating dashboard: {e}")
        
        # Print report (for cron delivery)
        print(report)
        
        return True
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = generate_report(include_dashboard_url=True)
    sys.exit(0 if success else 1)
