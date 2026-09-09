"""Local CLI: run the scan and write a self-contained preview into docs/.

The live site runs on Vercel (api/scan.py → Vercel Blob → public/index.html reads
/api/data). This CLI is for running the scan on your own machine — it reuses the exact
same pipeline, writes docs/data.json, and drops a copy of the real dashboard page next
to it wired to read that local file, so you can just open docs/index.html.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import CRITERIA
from .pipeline import scan_enriched

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scanner")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "docs"
PUBLIC_DIR = REPO_ROOT / "public"


def run(out_dir: Path, include_facebook: bool) -> list[dict]:
    listings = scan_enriched(allow_browser=True, include_apify=include_facebook)
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

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Local preview: the real page with the payload injected as window.__DATA__, so it
    # renders when opened directly as a file:// (where fetch() would be CORS-blocked).
    page = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
    inject = "<script>window.__DATA__ = " + json.dumps(payload, ensure_ascii=False) + ";</script>\n"
    leaflet_js = '<script src="/vendor/leaflet/leaflet.js"></script>'
    page = page.replace(leaflet_js, inject + leaflet_js, 1).replace('href="/favicon.svg"', 'href="favicon.svg"')
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / "favicon.svg").write_text((PUBLIC_DIR / "favicon.svg").read_text(encoding="utf-8"), encoding="utf-8")

    log.info("Wrote %d listings to %s", len(listings), out_dir)
    return listings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Dubai rental listings for flats matching your criteria.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory (default: ./docs)")
    parser.add_argument("--no-facebook", action="store_true", help="Skip Facebook/Apify even if a token is set")
    args = parser.parse_args()
    run(args.out, include_facebook=not args.no_facebook)
    return 0


if __name__ == "__main__":
    sys.exit(main())
