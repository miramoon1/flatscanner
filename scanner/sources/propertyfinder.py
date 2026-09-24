"""Property Finder scraper.

Property Finder server-renders its Next.js search pages, embedding full results as
JSON in a `<script id="__NEXT_DATA__">` tag — no browser/JS execution is needed, plain
`requests` gets a 200 with everything we need. Verified live (Sept 2026):

- Bedroom filtering only works through the URL *path* slug, not query params, e.g.
  `/en/rent/dubai/2-bedroom-apartments-for-rent.html` — query-string filters like
  `filter[max_price]` or `pmx=` are silently ignored server-side (they're echoed back
  into `searchQuery` but don't change the results), so don't rely on them.
- `?ob=pa` (order by price ascending) DOES work as a query param on top of that slug,
  and `?page=N` paginates correctly. Bathrooms and location aren't filterable via the
  URL at all, so we filter for those (and the real budget/area rules) client-side, same
  as scanner.filters does again afterwards on the merged results.

Because results come back cheapest-first, we can stop paging as soon as prices run well
past the budget instead of walking the entire (huge) 2-bedroom-in-Dubai catalog.
"""
from __future__ import annotations

import json
import re

import requests

from ..config import Criteria
from ..models import Listing
from . import Source

BASE_URL = "https://www.propertyfinder.ae/en/rent/dubai/{slug}-apartments-for-rent.html"


def _bedroom_slug(n: int) -> str:
    # Property Finder's URL path slug: "studio" for 0 bedrooms, "N-bedroom" otherwise.
    return "studio" if n == 0 else f"{n}-bedroom"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
# Results come back sorted price-ascending. Because the exact-2-bathroom filter makes
# matches sparse, they span ~15 pages of results, so we fetch this many. We fetch them
# CONCURRENTLY (not one-by-one) so it stays ~2-3s total instead of ~15s sequential —
# which matters on a serverless function with a hard time limit (the old sequential walk
# contributed to Vercel 504 timeouts).
MAX_PAGES = 16
FETCH_WORKERS = 10
# Soft time budget for the whole PF fetch. If a large profile (the Jumeirah "everything"
# scan does dozens of page requests) runs long — Vercel→PF is slower and rate-limited under
# load — stop and return whatever came back instead of letting the outer deadline abandon
# the source and yield ZERO. Kept under the function's ~55s scan window.
FETCH_BUDGET_SECONDS = 40


class PropertyFinderSource(Source):
    name = "propertyfinder"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # One or more bedroom searches depending on the profile: the main 2-bed scan is a
        # single slug; the Jumeirah profile (bedrooms_allowed=(0,1)) fetches studio + 1-bed.
        bedroom_counts = criteria.bedrooms_allowed or (criteria.bedrooms,)
        urls = [BASE_URL.format(slug=_bedroom_slug(n)) for n in bedroom_counts]
        orderings = getattr(criteria, "pf_orderings", ("pa",))
        max_pages = getattr(criteria, "pf_max_pages", MAX_PAGES)
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "en"}

        # (url, ob, page) work items — every bedroom search × sort order × page, concurrent.
        jobs = [(url, ob, page)
                for url in urls for ob in orderings for page in range(1, max_pages + 1)]

        def fetch_page(job: tuple[str, str, int]) -> list[dict]:
            url, ob, page = job
            resp = requests.get(url, params={"ob": ob, "page": page}, headers=headers, timeout=12)
            if resp.status_code != 200:
                return []
            return _extract_properties(resp.text)

        listings: list[Listing] = []
        deadline = time.monotonic() + FETCH_BUDGET_SECONDS
        # Don't use the pool as a context manager: its __exit__ joins ALL workers, which would
        # block past our budget. Submit, collect as they finish until the budget, then abandon
        # the rest (cancel_futures) and return the partial result — never zero on a slow run.
        pool = ThreadPoolExecutor(max_workers=FETCH_WORKERS)
        try:
            futures = [pool.submit(fetch_page, job) for job in jobs]
            for fut in as_completed(futures):
                try:
                    props = fut.result()
                except Exception:  # noqa: BLE001 — one bad page shouldn't sink the scan
                    props = []
                for prop in props:
                    listing = _to_listing(prop)
                    if listing is not None:
                        listings.append(listing)
                if time.monotonic() > deadline:
                    break
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return listings


def _extract_properties(html: str) -> list[dict]:
    match = NEXT_DATA_RE.search(html)
    if not match:
        return []
    data = json.loads(match.group(1))
    search_result = data.get("props", {}).get("pageProps", {}).get("searchResult", {})
    out = []
    for item in search_result.get("listings", []):
        if item.get("listing_type") == "property" and item.get("property"):
            out.append(item["property"])
    return out


def _to_listing(prop: dict) -> Listing | None:
    price = prop.get("price") or {}
    value = price.get("value")
    period = (price.get("period") or "").lower()

    if value is None:
        price_monthly = None
    elif period == "monthly":
        price_monthly = float(value)
    elif period == "yearly":
        price_monthly = float(value) / 12
    elif period == "weekly":
        price_monthly = float(value) * 52 / 12
    elif period == "daily":
        price_monthly = float(value) * 365 / 12
    else:
        price_monthly = None

    bedrooms = _to_int(prop.get("bedrooms"))
    bathrooms = _to_int(prop.get("bathrooms"))
    location = prop.get("location") or {}
    images = prop.get("images") or []
    image_url = images[0].get("medium") if images else None
    coordinates = location.get("coordinates") or {}

    return Listing(
        source="propertyfinder",
        source_id=str(prop.get("id")),
        title=prop.get("title") or "",
        url=prop.get("share_url") or "",
        price_monthly_aed=price_monthly,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area=location.get("full_name") or location.get("path_name") or "",
        image_url=image_url,
        listed_at=prop.get("listed_date"),
        latitude=coordinates.get("lat"),
        longitude=coordinates.get("lon"),
    )


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
