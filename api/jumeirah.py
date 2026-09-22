"""Vercel serverless function: the SECOND search profile — studio / 1-bed / room anywhere
on the Dubai coastal Jumeirah strip (see scanner.config.JUMEIRAH_CRITERIA).

Same shape and caching as api/data.py, but scoped to the Jumeirah profile and Property
Finder only (free HTTP — no Apify, no cost). The dashboard's "Jumeirah" tab reads this.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

for _root in (
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    os.getcwd(),
    "/var/task",
):
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)

from scanner.config import JUMEIRAH_CRITERIA  # noqa: E402
from scanner.pipeline import scan_enriched  # noqa: E402

CACHE_CONTROL = "public, s-maxage=604800"
SCAN_DEADLINE_SECONDS = 55


def _scan() -> dict:
    stats: dict = {}
    listings = scan_enriched(
        allow_browser=False, include_apify=False, stats=stats,
        deadline_seconds=SCAN_DEADLINE_SECONDS, criteria=JUMEIRAH_CRITERIA,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": "jumeirah",
        "criteria": {
            "max_price_monthly_aed": JUMEIRAH_CRITERIA.max_price_monthly_aed,
            "bedrooms_allowed": list(JUMEIRAH_CRITERIA.bedrooms_allowed or ()),
        },
        "count": len(listings),
        "sources": stats,
        "listings": listings,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import parse_qs, urlparse
        fresh = "fresh" in parse_qs(urlparse(self.path).query)
        try:
            payload = _scan()
            self.send_response(200)
            self.send_header("cache-control", "no-store" if fresh else CACHE_CONTROL)
        except Exception as e:
            import traceback
            payload = {
                "generated_at": None, "count": 0, "listings": [], "criteria": None,
                "profile": "jumeirah", "error": str(e),
                "trace": traceback.format_exc().splitlines()[-4:],
            }
            self.send_response(200)
            self.send_header("cache-control", "no-store")

        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
