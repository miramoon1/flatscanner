"""Vercel serverless function: the dashboard's data source.

Zero-config by design — no database, no Blob store, no secrets. It runs the scan on
demand and returns the results, with a CDN cache header so Vercel caches the response at
the edge. So the *first* request after the cache expires pays for one scan (~15s) and
every request after that is served instantly from cache until it goes stale. A daily
Vercel Cron (see vercel.json) hits this same endpoint to refresh the cache proactively,
so in practice visitors basically never wait on a cold scan.

Runs browserless (allow_browser=False): Property Finder over HTTP always; Facebook (and
Bayut/Dubizzle) via Apify only when their env vars are set. `sources` in the response
shows per-source fetched/matched/error so you can see at a glance whether Facebook etc.
returned anything.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.config import CRITERIA  # noqa: E402
from scanner.pipeline import scan_enriched  # noqa: E402

# Cache the scan result at Vercel's edge for 6h; keep serving the stale copy for another
# 18h while a fresh one is fetched in the background. Tunes how fresh vs. how snappy.
CACHE_CONTROL = "public, s-maxage=21600, stale-while-revalidate=64800"


def _scan() -> dict:
    stats: dict = {}
    listings = scan_enriched(include_facebook=True, allow_browser=False, stats=stats)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "max_price_monthly_aed": CRITERIA.max_price_monthly_aed,
            "bedrooms": CRITERIA.bedrooms,
            "bathrooms": CRITERIA.bathrooms,
        },
        "count": len(listings),
        "sources": stats,
        "listings": listings,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = _scan()
            self.send_response(200)
            self.send_header("cache-control", CACHE_CONTROL)
        except Exception as e:
            import traceback

            payload = {
                "generated_at": None, "count": 0, "listings": [], "criteria": None,
                "error": str(e), "trace": traceback.format_exc().splitlines()[-4:],
            }
            self.send_response(200)  # still render the page; surface the error in payload
            self.send_header("cache-control", "no-store")

        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
