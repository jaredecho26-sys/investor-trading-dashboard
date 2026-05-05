#!/usr/bin/env python3
"""
Fetch all orders from Schwab API and cache them locally.
Runs daily or on-demand to keep orders.json up-to-date with real fills.
"""

import json
import urllib.request
import urllib.parse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from schwab_token_utils import get_fresh_access_token

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = Path(os.path.expanduser("~/clawd/memory"))
CACHE_FILE = MEMORY_DIR / "all_orders_cache.json"

INCEPTION_DATE = "2025-10-15"

def fetch_orders(from_date, to_date):
    """
    Fetch orders from Schwab API.
    from_date, to_date: ISO format strings (YYYY-MM-DD)
    """
    access_token = get_fresh_access_token()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    # Construct datetime range with timezone
    # Parse dates and add timezone info
    from_dt = datetime.fromisoformat(from_date + 'T00:00:00').replace(tzinfo=timezone.utc).astimezone()
    to_dt = datetime.fromisoformat(to_date + 'T23:59:59').replace(tzinfo=timezone.utc).astimezone()
    
    # Fetch orders directly from Schwab API
    orders_url = "https://api.schwabapi.com/trader/v1/orders"
    params = {
        'fromEnteredTime': from_dt.isoformat(),
        'toEnteredTime': to_dt.isoformat(),
        'maxResults': 500,
        'status': 'FILLED'
    }
    
    query_string = urllib.parse.urlencode(params)
    full_url = f"{orders_url}?{query_string}"
    
    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            orders_data = json.loads(response.read().decode('utf-8'))
        
        # Schwab API returns a list of orders directly
        return orders_data if isinstance(orders_data, list) else (orders_data.get('orders', []) if isinstance(orders_data, dict) else [])
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[!] HTTP Error: {e.code}", file=sys.stderr)
        print(f"    Response: {error_body}", file=sys.stderr)
        raise Exception(f"Failed to fetch orders: {error_body}")

def extract_order_fields(order):
    """
    Extract relevant fields from a Schwab order.
    Maps Schwab API fields to our simplified structure.
    """
    try:
        # Parse entered time - handle both Z and +0000 formats
        entered_time_str = order.get('enteredTime', '')
        if entered_time_str:
            # Replace both Z and +0000 with +00:00 for consistent parsing
            normalized_time_str = entered_time_str.replace('Z', '+00:00')
            # Also handle the +0000 format from Schwab
            if normalized_time_str.endswith('+0000'):
                normalized_time_str = normalized_time_str[:-5] + '+00:00'
            entered_time = datetime.fromisoformat(normalized_time_str)
        else:
            entered_time = None
        
        # Extract symbol from leg (first leg if multiple)
        symbol = "UNKNOWN"
        if 'orderLegCollection' in order and order['orderLegCollection']:
            symbol = order['orderLegCollection'][0].get('instrument', {}).get('symbol', 'UNKNOWN')
        
        # Determine side (BUY or SELL)
        side = order.get('orderType', '').upper()
        if side not in ['BUY', 'SELL']:
            side = order.get('direction', 'BUY').upper()
        
        # Get execution details if filled - look for filled price and quantity
        quantity = float(order.get('quantity', 0))
        price = 0.0
        
        # Try to get price from various fields
        price = float(order.get('price', 0) or 0)
        if price == 0:
            price = float(order.get('filledPrice', 0) or order.get('stopPrice', 0) or 0)
        
        # If we have child orders (multi-leg), accumulate their details
        if 'childOrderStrategies' in order and order['childOrderStrategies']:
            child_quantities = 0
            for child in order['childOrderStrategies']:
                child_quantities += float(child.get('quantity', 0))
            if child_quantities > 0:
                quantity = child_quantities
        
        return {
            'orderTime': entered_time.isoformat() if entered_time else '',
            'order_date': entered_time.strftime('%Y-%m-%d') if entered_time else '',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'status': order.get('status', 'UNKNOWN'),
            'orderType': order.get('orderType', 'UNKNOWN'),
        }
    except Exception as e:
        print(f"[!] Error extracting fields from order: {e}", file=sys.stderr)
        print(f"    Order time: {order.get('enteredTime', 'N/A')}", file=sys.stderr)
        return None

def cache_orders(orders):
    """Save orders to local cache file"""
    # Ensure memory dir exists
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Extract and clean orders
    cleaned_orders = []
    for order in orders:
        extracted = extract_order_fields(order)
        if extracted:
            cleaned_orders.append(extracted)
    
    # Sort by orderTime
    cleaned_orders.sort(key=lambda o: o['orderTime'])
    
    # Write cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(cleaned_orders, f, indent=2)
    
    os.chmod(CACHE_FILE, 0o600)
    
    return len(cleaned_orders)

def main():
    """Fetch and cache all orders from inception date to today"""
    try:
        print(f"📥 Fetching orders from Schwab API...")
        print(f"   From: {INCEPTION_DATE}")
        print(f"   To:   {datetime.now().strftime('%Y-%m-%d')}")
        
        # Calculate date range (use timezone-aware datetime)
        from_date = INCEPTION_DATE
        to_date = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')
        
        # Fetch orders
        orders = fetch_orders(from_date, to_date)
        print(f"✓ Fetched {len(orders)} filled orders from Schwab")
        
        # Cache orders
        cached_count = cache_orders(orders)
        print(f"✓ Cached {cached_count} orders to {CACHE_FILE}")
        
        # Print summary
        if cached_count > 0:
            with open(CACHE_FILE) as f:
                cached_data = json.load(f)
            
            symbols = set(o['symbol'] for o in cached_data if o.get('symbol') != 'UNKNOWN')
            print(f"\n📊 Summary:")
            print(f"   Total orders: {len(cached_data)}")
            if symbols:
                print(f"   Symbols: {', '.join(sorted(symbols)[:20])}")
            
            # Show date range
            if cached_data:
                first_order = cached_data[0].get('orderTime', 'N/A')
                last_order = cached_data[-1].get('orderTime', 'N/A')
                print(f"   Date range: {first_order[:10] if first_order != 'N/A' else 'N/A'} to {last_order[:10] if last_order != 'N/A' else 'N/A'}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
