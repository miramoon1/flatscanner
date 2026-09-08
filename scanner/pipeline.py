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

    if include_facebook:
        from pathlib import Path

        # Local saved-login Playwright fallback only when there's no Apify token AND we
        # can run a browser; otherwise use the Apify variant. The Apify variant is added
        # even without a token so it reports a clear "set APIFY_API_TOKEN" error in the
        # diagnostics instead of Facebook silently disappearing from the source list.
        if not os.environ.get("APIFY_API_TOKEN") and allow_browser \
                and (Path(__file__).resolve().parent.parent / "fb_state.json").exists():
            from .sources.facebook import FacebookMarketplaceSource

            sources.append(FacebookMarketplaceSource())
        else:
            from .sources.facebook_apify import FacebookApifySource

            sources.append(FacebookApifySource())

    return sources


def collect(include_facebook: bool = True, allow_browser: bool = True, stats: dict | None = None) -> list[Listing]:
    """Return filtered + ranked Listings from every available source.

    `stats`, if given, is populated with per-source diagnostics:
    {source_name: {"fetched": int, "matched": int, "error": str | None}}. This is what
    /api/scan surfaces so "0 listings" can be told apart from "a source errored".
    """
    all_listings: list[Listing] = []
    per_source: dict[str, list[Listing]] = {}
    for source in load_sources(include_facebook, allow_browser):
        try:
            log.info("Fetching from %s...", source.name)
            listings = source.fetch(CRITERIA)
            log.info("%s: got %d listings", source.name, len(listings))
            per_source.setdefault(source.name, []).extend(listings)
            all_listings.extend(listings)
            if stats is not None:
                stats.setdefault(source.name, {"fetched": 0, "matched": 0, "error": None})
                stats[source.name]["fetched"] += len(listings)
        except Exception as e:
            log.exception("Source %s failed, skipping it for this run", source.name)
            if stats is not None:
                stats.setdefault(source.name, {"fetched": 0, "matched": 0, "error": None})
                stats[source.name]["error"] = f"{type(e).__name__}: {e}"

    seen: set[tuple[str, str]] = set()
    deduped: list[Listing] = []
    for l in all_listings:
        key = (l.source, l.source_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    matches = filter_and_rank(deduped, CRITERIA)
    if stats is not None:
        for m in matches:
            if m.source in stats:
                stats[m.source]["matched"] += 1
    log.info("%d / %d listings match the criteria", len(matches), len(deduped))
    return matches


def scan_enriched(include_facebook: bool = True, allow_browser: bool = True, stats: dict | None = None) -> list[dict]:
    """collect() plus per-listing enrichment — the exact records the dashboard reads."""
    return [enrich(l) for l in collect(include_facebook, allow_browser, stats=stats)]
