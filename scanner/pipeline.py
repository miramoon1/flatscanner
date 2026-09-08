"""Run the sources, filter, rank, and enrich — the shared core behind both the local
CLI (scanner/main.py) and the Vercel serverless scan (api/scan.py)."""
from __future__ import annotations

import logging
import os

from .config import CRITERIA
from .enrich import enrich
from .filters import filter_and_rank
from .models import Listing

log = logging.getLogger("scanner")


def load_sources(include_facebook: bool, allow_browser: bool):
    """Assemble the source list.

    allow_browser: whether Playwright-based sources (Bayut/Dubizzle) may be used. On
    Vercel this is False — serverless can't launch a headless browser — so those two
    only run when routed through Apify (env APIFY_BAYUT_ACTOR / APIFY_DUBIZZLE_ACTOR),
    handled inside their Apify variants. See api/scan.py.
    """
    from .sources.propertyfinder import PropertyFinderSource

    sources = [PropertyFinderSource()]

    if allow_browser:
        from .sources.bayut import BayutSource
        from .sources.dubizzle import DubizzleSource

        sources += [BayutSource(), DubizzleSource()]
    else:
        # Apify-backed Bayut/Dubizzle, only if an actor id is configured for each.
        if os.environ.get("APIFY_BAYUT_ACTOR"):
            from .sources.bayut_apify import BayutApifySource

            sources.append(BayutApifySource())
        if os.environ.get("APIFY_DUBIZZLE_ACTOR"):
            from .sources.dubizzle_apify import DubizzleApifySource

            sources.append(DubizzleApifySource())

    if include_facebook and os.environ.get("APIFY_API_TOKEN"):
        from .sources.facebook_apify import FacebookApifySource

        sources.append(FacebookApifySource())
    elif include_facebook and allow_browser:
        from pathlib import Path

        if (Path(__file__).resolve().parent.parent / "fb_state.json").exists():
            from .sources.facebook import FacebookMarketplaceSource

            sources.append(FacebookMarketplaceSource())

    return sources


def collect(include_facebook: bool = True, allow_browser: bool = True) -> list[Listing]:
    """Return filtered + ranked Listings from every available source."""
    all_listings: list[Listing] = []
    for source in load_sources(include_facebook, allow_browser):
        try:
            log.info("Fetching from %s...", source.name)
            listings = source.fetch(CRITERIA)
            log.info("%s: got %d listings", source.name, len(listings))
            all_listings.extend(listings)
        except Exception:
            log.exception("Source %s failed, skipping it for this run", source.name)

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
    return matches


def scan_enriched(include_facebook: bool = True, allow_browser: bool = True) -> list[dict]:
    """collect() plus per-listing enrichment — the exact records the dashboard reads."""
    return [enrich(l) for l in collect(include_facebook, allow_browser)]
