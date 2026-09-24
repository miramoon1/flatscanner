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


def load_sources(allow_browser: bool, include_apify: bool):
    """Assemble the source list.

    allow_browser: whether Playwright-based sources (Bayut/Dubizzle) may run. On Vercel
    this is False — serverless can't launch a headless browser.

    include_apify: whether PAID Apify-backed sources (Facebook, and Bayut/Dubizzle via
    Apify) may run. This is the cost gate: every Apify run consumes credit, so these
    NEVER run on a plain page load or default scan — only when the user explicitly asks
    for them (api/data.py sets this from an ?apify=1 query param, i.e. the dedicated
    "Include Facebook" button). Property Finder is free HTTP and always runs.
    """
    from .sources.propertyfinder import PropertyFinderSource

    sources = [PropertyFinderSource()]

    # Local dev only: real browser scrapers for Bayut/Dubizzle (free, no Apify).
    if allow_browser:
        from .sources.bayut import BayutSource
        from .sources.dubizzle import DubizzleSource

        sources += [BayutSource(), DubizzleSource()]

    # Paid Apify sources — only when explicitly requested.
    if include_apify:
        # Bayut stays OPT-IN behind its env var — the only working actor is very pricey.
        if os.environ.get("APIFY_BAYUT_ACTOR"):
            from .sources.bayut_apify import BayutApifySource

            sources.append(BayutApifySource())
        # Dubizzle runs by default (cheap actor, ~$1.50/1000) — no extra env var needed,
        # just the same APIFY_API_TOKEN that Facebook uses. Override actor via env if wanted.
        from .sources.dubizzle_apify import DubizzleApifySource

        sources.append(DubizzleApifySource())

        from pathlib import Path

        if not os.environ.get("APIFY_API_TOKEN") and allow_browser \
                and (Path(__file__).resolve().parent.parent / "fb_state.json").exists():
            from .sources.facebook import FacebookMarketplaceSource

            sources.append(FacebookMarketplaceSource())
        else:
            from .sources.facebook_apify import FacebookApifySource

            sources.append(FacebookApifySource())

    return sources


def collect(
    allow_browser: bool = True,
    include_apify: bool = False,
    stats: dict | None = None,
    deadline_seconds: float | None = None,
    criteria=CRITERIA,
) -> list[Listing]:
    """Return filtered + ranked Listings from every available source.

    Sources run CONCURRENTLY and, if `deadline_seconds` is set, under a hard overall
    budget: whatever has returned by the deadline is used, and any source still running
    (e.g. a slow Apify actor run) is recorded as timed-out rather than being allowed to
    hang the request past a serverless function's limit and 504.

    `stats`, if given, is populated with per-source diagnostics:
    {source_name: {"fetched": int, "matched": int, "error": str | None}}.
    """
    import threading
    import time

    sources = load_sources(allow_browser, include_apify)
    all_listings: list[Listing] = []

    def _stat(name):
        if stats is not None:
            stats.setdefault(name, {"fetched": 0, "matched": 0, "error": None})
            return stats[name]
        return None

    # DAEMON threads, deliberately — not ThreadPoolExecutor. A pool's worker threads are
    # non-daemon and get joined both by shutdown(wait=True) AND by concurrent.futures'
    # atexit hook, so a source still mid-run (a slow Apify actor call) blocks past the
    # deadline and 504s the request. Daemon threads are never joined by anyone: we wait
    # for each only up to the remaining budget, then move on and return; a straggler is
    # abandoned and dies with the worker. This is what actually enforces the deadline.
    results: dict[str, object] = {}  # name -> list[Listing] | Exception

    def _run(src):
        try:
            results[src.name] = src.fetch(criteria)
        except Exception as e:  # noqa: BLE001 — recorded per-source below
            results[src.name] = e

    threads = []
    for s in sources:
        _stat(s.name)  # ensure every source appears in stats, even if it times out
        t = threading.Thread(target=_run, args=(s,), daemon=True)
        t.start()
        threads.append((t, s))

    deadline = (time.monotonic() + deadline_seconds) if deadline_seconds else None
    for t, source in threads:
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        t.join(remaining)

    for _t, source in threads:
        st = _stat(source.name)
        outcome = results.get(source.name)
        if outcome is None:  # thread hadn't recorded anything by the deadline
            log.warning("Source %s did not finish within the %ss budget", source.name, deadline_seconds)
            if st is not None:
                st["error"] = f"timed out (slower than the {deadline_seconds}s scan budget)"
        elif isinstance(outcome, Exception):
            log.warning("Source %s failed: %s", source.name, outcome)
            if st is not None:
                st["error"] = f"{type(outcome).__name__}: {outcome}"
        else:
            log.info("%s: got %d listings", source.name, len(outcome))
            all_listings.extend(outcome)
            if st is not None:
                st["fetched"] += len(outcome)

    seen: set[tuple[str, str]] = set()
    deduped: list[Listing] = []
    for l in all_listings:
        key = (l.source, l.source_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(l)

    matches = filter_and_rank(deduped, criteria)
    if stats is not None:
        for m in matches:
            if m.source in stats:
                stats[m.source]["matched"] += 1
    log.info("%d / %d listings match the criteria", len(matches), len(deduped))
    return matches


def scan_enriched(
    allow_browser: bool = True,
    include_apify: bool = False,
    stats: dict | None = None,
    deadline_seconds: float | None = None,
    criteria=CRITERIA,
) -> list[dict]:
    """collect() plus per-listing enrichment — the exact records the dashboard reads."""
    return [
        enrich(l, criteria)
        for l in collect(allow_browser, include_apify, stats=stats,
                         deadline_seconds=deadline_seconds, criteria=criteria)
    ]
