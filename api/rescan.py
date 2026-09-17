"""Vercel serverless function: kick off the free Bayut & Dubizzle scrape.

The dashboard's "Refresh Bayut & Dubizzle" button POSTs here. A static site can't
start a GitHub job on its own, so this thin endpoint calls GitHub's workflow_dispatch
API to run .github/workflows/scrape-browser-sources.yml on a real-browser runner (free,
no Apify). It needs a GitHub token with Actions: write on the repo, provided as the
GH_DISPATCH_TOKEN env var in Vercel. Without it, the button still works but returns a
clear "not configured yet" message instead of doing anything — so nothing here can ever
incur a cost.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

REPO = os.environ.get("GH_REPO", "miramoon1/flatscanner")
WORKFLOW_FILE = os.environ.get("GH_WORKFLOW_FILE", "scrape-browser-sources.yml")
REF = os.environ.get("GH_REF", "main")


def _dispatch() -> dict:
    token = os.environ.get("GH_DISPATCH_TOKEN")
    if not token:
        return {
            "ok": False,
            "reason": "no_token",
            "message": (
                "The refresh button isn't connected yet. In Vercel, add an environment "
                "variable GH_DISPATCH_TOKEN set to a GitHub token with 'Actions: write' "
                "on this repo, then redeploy. (You can always run it from the repo's "
                "Actions tab in the meantime.)"
            ),
        }

    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    data = json.dumps({"ref": REF}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "flatscanner-dashboard",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status in (201, 204):
                return {"ok": True}
            return {"ok": False, "reason": "unexpected_status",
                    "message": f"GitHub returned HTTP {r.status}."}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return {
            "ok": False,
            "reason": "http_error",
            "status": e.code,
            "message": (
                f"GitHub rejected the request (HTTP {e.code}). Make sure GH_DISPATCH_TOKEN "
                f"has 'Actions: write' on {REPO} and hasn't expired. {detail}"
            ),
        }
    except Exception as e:  # noqa: BLE001 — report, never crash the endpoint
        return {"ok": False, "reason": "error", "message": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self._respond(_dispatch())

    def do_GET(self):  # noqa: N802 — allow GET too, for easy manual testing
        self._respond(_dispatch())

    def _respond(self, payload: dict) -> None:
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
