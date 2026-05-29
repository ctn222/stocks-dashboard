#!/usr/bin/env python3
"""Minimal static file server scoped to the project directory.

Use this if you'd rather not rely on file:// — e.g. when extending the
dashboard to fetch data.csv directly over fetch()/XHR.

    python3 serve.py
    # then open http://127.0.0.1:8767/dashboard.html
"""
import http.server
import os
import socketserver
import sys
from pathlib import Path

PORT = int(os.environ.get("PORT", "8767"))
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Serving {ROOT} at http://127.0.0.1:{PORT}")
    sys.stdout.flush()
    httpd.serve_forever()
