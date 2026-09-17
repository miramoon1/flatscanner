"""Scrape the browser-only sources (Bayut, Dubizzle) with Playwright and write the
results to public/browser_sources.json.

This runs in GitHub Actions (free browser runner), NOT on Vercel — Vercel serverless
can't launch a browser, and the Apify alternative for these two costs money. Bayut and
Dubizzle sit behind bot-management (a JS challenge / Imperva Incapsula), so even a real
browser from a datacenter IP may get blocked; if so, the file is written with empty
results and an error note rather than crashing, and the dashboard simply shows nothing
for that source. Property Finder (free HTTP) and Facebook (Apify, on demand) are handled
separately by the Vercel function — this script is only the free Bayut/Dubizzle feed.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanner.config import CRITERIA  # noqa: E402
from scanner.enrich import enrich  # noqa: E402
from scanner.filters import filter_and_rank  # noqa: E402
from scanner.sources.bayut import BayutSource  # noqa: E402
from scanner.sources.dubizzle import DubizzleSource  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scrape")

OUT = Path(__file__).resolve().parent.parent / "public" / "browser_sources.json"


def main() -> None:
    all_listings = []
    stats: dict = {}
    for source in (BayutSource(), DubizzleSource()):
        try:
            log.info("Scraping %s...", source.name)
            got = source.fetch(CRITERIA)
            diag = getattr(source, "diagnostic", None)
            log.info("%s: %d listings | diagnostic=%s", source.name, len(got), diag)
            all_listings.extend(got)
            stats[source.name] = {"fetched": len(got), "matched": 0, "error": None, "diagnostic": diag}
        except Exception as e:  # noqa: BLE001 — recorded, never fatal
            log.exception("%s failed", source.name)
            stats[source.name] = {
                "fetched": 0, "matched": 0, "error": f"{type(e).__name__}: {e}",
                "diagnostic": getattr(source, "diagnostic", None),
            }

    matches = filter_and_rank(all_listings, CRITERIA)
    for m in matches:
        if m.source in stats:
            stats[m.source]["matched"] += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": stats,
        "listings": [enrich(m) for m in matches],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %d listings to %s", len(payload["listings"]), OUT)


if __name__ == "__main__":
    main()
