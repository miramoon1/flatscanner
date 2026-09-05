from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .config import CRITERIA
from .dashboard import render_dashboard
from .filters import filter_and_rank
from .models import Listing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scanner")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "docs"
FB_STATE_PATH = REPO_ROOT / "fb_state.json"


def load_sources(include_facebook: bool):
    from .sources.bayut import BayutSource
    from .sources.dubizzle import DubizzleSource
    from .sources.propertyfinder import PropertyFinderSource

    sources = [BayutSource(), DubizzleSource(), PropertyFinderSource()]

    if include_facebook:
        # Prefer Apify (no personal Facebook login/ban exposure) over the
        # Playwright + saved-login fallback. See scanner/sources/facebook_apify.py
        # and scanner/sources/facebook.py for why.
        if os.environ.get("APIFY_API_TOKEN"):
            from .sources.facebook_apify import FacebookApifySource

            sources.append(FacebookApifySource())
        elif FB_STATE_PATH.exists():
            from .sources.facebook import FacebookMarketplaceSource

            sources.append(FacebookMarketplaceSource())
        else:
            log.warning(
                "--with-facebook was passed but neither APIFY_API_TOKEN nor fb_state.json "
                "is set up — skipping Facebook this run. See README."
            )

    return sources


def run(out_dir: Path, include_facebook: bool) -> list[Listing]:
    all_listings: list[Listing] = []

    for source in load_sources(include_facebook):
        try:
            log.info("Fetching from %s...", source.name)
            listings = source.fetch(CRITERIA)
            log.info("%s: got %d listings", source.name, len(listings))
            all_listings.extend(listings)
        except Exception:
            log.exception("Source %s failed, skipping it for this run", source.name)

    # de-dupe by (source, source_id)
    seen: set[tuple[str, str]] = set()
    deduped: list[Listing] = []
    for l in all_listings:
        key = (l.source, l.source_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    matches = filter_and_rank(deduped, CRITERIA)
    log.info("%d / %d listings match the criteria", len(matches), len(deduped))

    render_dashboard(matches, CRITERIA, out_dir)
    log.info("Dashboard written to %s", out_dir)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Dubai rental listings for flats matching your criteria.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for the dashboard (default: ./docs)")
    parser.add_argument("--with-facebook", action="store_true", help="Also attempt Facebook Marketplace (requires a saved login session, see README)")
    args = parser.parse_args()

    run(args.out, args.with_facebook)
    return 0


if __name__ == "__main__":
    sys.exit(main())
