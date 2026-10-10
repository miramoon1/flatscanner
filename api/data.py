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

# Make the sibling `scanner/` package importable regardless of Vercel's bundle layout
# (vercel.json includeFiles ships it; add likely roots to the path to be safe).
for _root in (
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # repo root (../ from api/)
    os.getcwd(),
    "/var/task",  # Vercel/Lambda deployment root
):
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)

from scanner.config import CRITERIA  # noqa: E402
from scanner.pipeline import scan_enriched  # noqa: E402
# Scans are button-triggered (the dashboard's "Scan now" calls /api/data?fresh=<ts>,
# a unique URL that bypasses this cache). A plain page-load GET is served from the last
# scan's cached copy for a long window, so simply opening the site never kicks off a
# scan (or an Apify charge) on its own — only the button does. If the cache does lapse
# (7 days), the next load runs one scan to refresh it.
CACHE_CONTROL = "public, s-maxage=604800"


# Hard scan budget, just under the function's maxDuration (60s in vercel.json). Sources
# still running at this point are reported as timed-out; whatever finished is returned,
# so a slow Apify actor can't 504 the whole request. Set close to the 60s ceiling to
# give the Facebook Apify run the best chance of finishing inline.
SCAN_DEADLINE_SECONDS = 55


def _criteria_from_params(params: dict) -> "object":
    """Build a Criteria from the setup-wizard query params, falling back to CRITERIA.

    Lets each user tune budget / bedrooms / bathrooms / the Creek cutoff from the in-app
    Setup screen without editing code or redeploying. params is parse_qs output (lists).
    """
    from dataclasses import replace

    def _one(key):
        v = params.get(key, [None])[0]
        return v.strip() if isinstance(v, str) else v

    overrides: dict = {}

    mp = _one("max_price")
    if mp and mp.isdigit():
        overrides["max_price_monthly_aed"] = int(mp)

    beds = _one("bedrooms")  # "any" | "0" (studio) | "2" | "0,1,2"
    if beds:
        if beds == "any":
            overrides.update(any_bedrooms=True, allow_unknown_bedrooms=True,
                             bedrooms_allowed=(0, 1, 2, 3, 4))
        elif "," in beds:
            nums = tuple(int(x) for x in beds.split(",") if x.strip().isdigit())
            if nums:
                overrides["bedrooms_allowed"] = nums
        elif beds.isdigit():
            overrides.update(bedrooms=int(beds), bedrooms_allowed=None)

    baths = _one("bathrooms")  # "any" | "1" | "2" | "3"
    if baths == "any":
        overrides["bathrooms"] = None
    elif baths and baths.isdigit():
        overrides["bathrooms"] = int(baths)

    if _one("creek") in ("0", "false", "no", "off"):
        overrides["keep_sw_of_line"] = None  # show all Dubai, don't hide the Deira/Sharjah side

    farout = _one("farout")  # "1" = drop far-out Dubai areas, "0" = keep them
    if farout in ("1", "true", "yes", "on"):
        overrides["drop_far_out"] = True
    elif farout in ("0", "false", "no", "off"):
        overrides["drop_far_out"] = False

    em = _one("emirates")  # e.g. "dubai,sharjah,ajman"
    if em:
        from scanner.config import EMIRATE_IDS
        chosen = tuple(e for e in (x.strip().lower() for x in em.split(",")) if e in EMIRATE_IDS)
        if chosen:
            overrides["emirates"] = chosen

    return replace(CRITERIA, **overrides) if overrides else CRITERIA


def _scan(include_apify: bool, criteria=None) -> dict:
    criteria = criteria or CRITERIA
    stats: dict = {}
    listings = scan_enriched(
        allow_browser=False, include_apify=include_apify, stats=stats,
        deadline_seconds=SCAN_DEADLINE_SECONDS, criteria=criteria,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "max_price_monthly_aed": criteria.max_price_monthly_aed,
            "bedrooms": criteria.bedrooms,
            "bathrooms": criteria.bathrooms,
        },
        "count": len(listings),
        "sources": stats,
        "listings": listings,
        "included_apify": include_apify,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # PAID Apify sources (Facebook etc.) run ONLY when ?apify=1 is passed — i.e. the
        # dedicated "Include Facebook" button. Plain loads and normal "Scan now" never
        # touch Apify, so casual use costs nothing.
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(self.path).query)
        include_apify = params.get("apify", ["0"])[0] in ("1", "true", "yes")
        try:
            payload = _scan(include_apify, criteria=_criteria_from_params(params))
            self.send_response(200)
            # An Apify scan is a live paid run — never let a CDN serve it to others.
            self.send_header("cache-control", "no-store" if include_apify else CACHE_CONTROL)
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
