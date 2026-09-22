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


def _scan(include_apify: bool) -> dict:
    stats: dict = {}
    listings = scan_enriched(
        allow_browser=False, include_apify=include_apify, stats=stats,
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
        "included_apify": include_apify,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        # ?apify=1 also pulls the paid sources (Facebook/Dubizzle) — where the ROOMS are,
        # since Property Finder only lists whole units. Only when the button asks for it.
        include_apify = q.get("apify", ["0"])[0] in ("1", "true", "yes")
        fresh = "fresh" in q
        try:
            payload = _scan(include_apify)
            self.send_response(200)
            self.send_header("cache-control", "no-store" if (fresh or include_apify) else CACHE_CONTROL)
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
