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


def collect(
    include_facebook: bool = True,
    allow_browser: bool = True,
    stats: dict | None = None,
    deadline_seconds: float | None = None,
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

    sources = load_sources(include_facebook, allow_browser)
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
            results[src.name] = src.fetch(CRITERIA)
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

    matches = filter_and_rank(deduped, CRITERIA)
    if stats is not None:
        for m in matches:
            if m.source in stats:
                stats[m.source]["matched"] += 1
    log.info("%d / %d listings match the criteria", len(matches), len(deduped))
    return matches


def scan_enriched(
    include_facebook: bool = True,
    allow_browser: bool = True,
    stats: dict | None = None,
    deadline_seconds: float | None = None,
) -> list[dict]:
    """collect() plus per-listing enrichment — the exact records the dashboard reads."""
    return [enrich(l) for l in collect(include_facebook, allow_browser, stats=stats, deadline_seconds=deadline_seconds)]
