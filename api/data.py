"""Vercel serverless function: return the latest scan results for the dashboard.

The dashboard fetches this same-origin (/api/data) so it never needs to know the Blob
store's URL. We look up the stable `data.json` blob, fetch it, and return it with a
short CDN cache. If no scan has run yet, returns an empty-but-valid payload so the page
renders a clean "no listings yet" state instead of erroring.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

BLOB_PATHNAME = "data.json"
EMPTY = {"generated_at": None, "count": 0, "listings": [], "criteria": None}


def _load_latest() -> dict:
    import requests

    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        return EMPTY

    # Find the blob by pathname prefix, then fetch its content.
    listing = requests.get(
        "https://blob.vercel-storage.com",
        headers={"authorization": f"Bearer {token}"},
        params={"prefix": BLOB_PATHNAME, "limit": "1"},
        timeout=20,
    )
    listing.raise_for_status()
    blobs = listing.json().get("blobs", [])
    if not blobs:
        return EMPTY

    url = blobs[0].get("downloadUrl") or blobs[0].get("url")
    if not url:
        return EMPTY
    content = requests.get(url, timeout=20)
    content.raise_for_status()
    return content.json()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = _load_latest()
            status = 200
        except Exception as e:
            payload = {**EMPTY, "error": str(e)}
            status = 200  # still render the page; surface the error in the payload

        self.send_response(status)
        self.send_header("content-type", "application/json")
        # Cache at the edge for 5 min so a burst of viewers doesn't re-hit Blob each time.
        self.send_header("cache-control", "public, s-maxage=300, stale-while-revalidate=600")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
