#!/usr/bin/env python3
"""
Schwab API token management - handles automatic refresh with zero manual intervention
"""

import json
import urllib.request
import urllib.parse
import base64
import os
import sys
import time
from datetime import datetime

SECRETS_DIR = os.path.expanduser("~/clawd/secrets")
SCHWAB_ENV_FILE = os.path.join(SECRETS_DIR, "schwab.env")
SCHWAB_TOKEN_FILE = os.path.join(SECRETS_DIR, "schwab-token.json")

def read_env():
    """Read Schwab API credentials from env file"""
    env_vars = {}
    with open(SCHWAB_ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                env_vars[key] = val
    return env_vars

def read_token():
    """Read current token data"""
    with open(SCHWAB_TOKEN_FILE) as f:
        return json.load(f)

def write_token(token_data):
    """Write updated token data"""
    token_data = dict(token_data)
    token_data['saved_at_epoch'] = int(time.time())
    token_data['saved_at_iso'] = datetime.utcnow().isoformat() + 'Z'
    with open(SCHWAB_TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)
    os.chmod(SCHWAB_TOKEN_FILE, 0o600)

def refresh_token_if_needed():
    """
    Check if token is expired, refresh if needed.
    Returns: access_token (guaranteed fresh)
    """
    try:
        token_data = read_token()
        expires_in = int(token_data.get('expires_in', 0) or 0)
        saved_at_epoch = int(token_data.get('saved_at_epoch', 0) or 0)
        remaining = (saved_at_epoch + expires_in) - int(time.time()) if saved_at_epoch else 0

        # If token has >120 seconds remaining (2 min buffer), keep using it.
        if remaining > 120:
            return token_data['access_token']
        
        # Token expired or about to expire - refresh it
        return _do_refresh(token_data)
        
    except Exception as e:
        print(f"[!] Token refresh failed: {e}", file=sys.stderr)
        raise

def _do_refresh(token_data):
    """Perform the actual token refresh"""
    env_vars = read_env()
    API_KEY = env_vars.get('SCHWAB_API_KEY')
    API_SECRET = env_vars.get('SCHWAB_APP_SECRET')
    REFRESH_TOKEN = token_data.get('refresh_token')
    
    if not REFRESH_TOKEN:
        raise ValueError("No refresh_token available - need to re-authenticate")
    
    token_url = "https://api.schwabapi.com/v1/oauth/token"
    auth_string = f"{API_KEY}:{API_SECRET}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(token_url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            new_token_data = json.loads(response.read().decode('utf-8'))

        if 'refresh_token' not in new_token_data and REFRESH_TOKEN:
            new_token_data['refresh_token'] = REFRESH_TOKEN
        
        # Save the new tokens
        write_token(new_token_data)
        
        return new_token_data['access_token']
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"Token refresh failed: {error_body}")

def get_fresh_access_token():
    """
    Main entry point - returns a guaranteed-fresh access token
    Handles all refresh logic transparently
    """
    return refresh_token_if_needed()

if __name__ == '__main__':
    # Can be run standalone to test/force refresh
    token = get_fresh_access_token()
    print(f"✓ Fresh access token: {token[:50]}...")
