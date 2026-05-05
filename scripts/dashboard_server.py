#!/usr/bin/env python3
"""
Simple HTTP server to serve trading dashboard
Runs on localhost:8080 by default
Can be tunneled via ngrok for public access
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8080
DASHBOARD_DIR = os.path.expanduser("~/clawd/dashboards")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/trading-dashboard.html'
        return super().do_GET()
    
    def log_message(self, format, *args):
        """Log server messages to stdout"""
        print(f"[{self.log_date_time_string()}] {format % args}")

def start_server():
    """Start the dashboard server"""
    try:
        Handler = DashboardHandler
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"✓ Dashboard server running on http://localhost:{PORT}")
            print(f"✓ Serving from: {DASHBOARD_DIR}")
            print(f"✓ Open in browser: http://localhost:{PORT}")
            print(f"\n[Press Ctrl+C to stop]\n")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"✗ Port {PORT} is already in use")
            print(f"  Use: lsof -i :{PORT} to find the process")
            print(f"  Then: kill -9 <PID> to stop it")
        else:
            print(f"✗ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_server()
