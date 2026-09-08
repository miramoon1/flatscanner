"""Vercel serverless function: run the scan and write results to Vercel Blob.

Triggered by Vercel Cron (see vercel.json `crons`). Vercel Cron sends
`Authorization: Bearer <CRON_SECRET>`; when CRON_SECRET is set we require it, so the
endpoint can't be hammered publicly.

Runs with allow_browser=False — Vercel serverless can't launch a headless browser, so
Property Finder runs over plain HTTP and Bayut/Dubizzle/Facebook run via Apify (only the
ones whose actor/token env vars are set). Writes a single `data.json` blob at a stable
pathname; the dashboard reads it through /api/data.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.config import CRITERIA  # noqa: E402
from scanner.pipeline import scan_enriched  # noqa: E402

BLOB_PATHNAME = "data.json"


def _build_payload() -> tuple[dict, dict]:
    """Return (payload, per-source stats)."""
    stats: dict = {}
    listings = scan_enriched(include_facebook=True, allow_browser=False, stats=stats)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "max_price_monthly_aed": CRITERIA.max_price_monthly_aed,
            "bedrooms": CRITERIA.bedrooms,
            "bathrooms": CRITERIA.bathrooms,
        },
        "count": len(listings),
        "listings": listings,
    }
    return payload, stats


def _write_blob(payload: dict) -> str:
    """PUT the payload to Vercel Blob at a stable pathname; return the public URL."""
    import requests

    token = os.environ["BLOB_READ_WRITE_TOKEN"]
    resp = requests.put(
        f"https://blob.vercel-storage.com/{BLOB_PATHNAME}",
        headers={
            "authorization": f"Bearer {token}",
            "x-content-type": "application/json",
            "x-add-random-suffix": "0",  # stable pathname so /api/data can find it
            "x-cache-control-max-age": "300",
        },
        data=json.dumps(payload).encode("utf-8"),
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("url", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Auth: Vercel Cron sends `Authorization: Bearer <CRON_SECRET>`. For a manual
        # browser trigger you can instead pass `?key=<CRON_SECRET>`. If CRON_SECRET is
        # unset the endpoint is open (fine for a personal tool, but set it to be safe).
        secret = os.environ.get("CRON_SECRET")
        qs = parse_qs(urlparse(self.path).query)
        provided = self.headers.get("authorization") == f"Bearer {secret}" or qs.get("key", [""])[0] == secret
        if secret and not provided:
            self._respond(401, {"error": "unauthorized — add ?key=<CRON_SECRET> to trigger manually"})
            return

        try:
            payload, stats = _build_payload()
            url = _write_blob(payload)
            self._respond(200, {"ok": True, "count": payload["count"], "sources": stats, "blob_url": url})
        except Exception as e:  # surface the reason in the response + cron log
            import traceback

            self._respond(500, {"ok": False, "error": str(e), "trace": traceback.format_exc().splitlines()[-4:]})

    def _respond(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))
