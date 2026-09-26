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

        # Which PF listing pages to fetch, in priority order:
        #  - pf_location_ids set → the /en/search?c=2&l=<id> route, one base URL per
        #    community. This is a REAL location filter, so we get exactly those areas at
        #    every price. (c=2 = rent.) Used by the Jumeirah tab.
        #  - pf_monthly_price_search set → the Dubai-scoped /en/search price route, split
        #    into contiguous PRICE BANDS so the whole budget range is covered (see below).
        #    Used by the main tab.
        #  - pf_property_paths set → literal paths ("properties-for-rent.html" = all types).
        #  - otherwise → per-bedroom apartment URLs (the main 2-bed scan, etc.).
        loc_ids = getattr(criteria, "pf_location_ids", ()) or ()
        paths = getattr(criteria, "pf_property_paths", ()) or ()
        jum_supplement_urls: list[str] = []
        if loc_ids:
            urls = [f"https://www.propertyfinder.ae/en/search?c=2&l={lid}" for lid in loc_ids]
        elif getattr(criteria, "pf_monthly_price_search", False):
            # Dubai-scoped price search, split into contiguous price BANDS. Why bands:
            #  - l=1 = Dubai (the /en/rent/dubai slug's own searchQuery uses l:"1"), so this
            #    stays in Dubai instead of pulling Sharjah/Ajman like a bare c=2 search.
            #  - pf/pt are YEARLY bounds (PF quotes most rents per year), so ×12; PF
            #    normalises monthly-quoted listings into the same filter, and our own filter
            #    re-checks the true monthly price ≤ budget.
            #  - PF caps pagination at ~50 pages (~1250 results) per query, and Dubai has
            #    thousands of 2-beds in the 6–8k band — so a single cheapest-first query
            #    can't reach past ~6.7k. Splitting the range into ≤6k + 500/mo steps means
            #    each band's cheapest-first pages land in that band, covering the whole
            #    0→budget range instead of stalling at the cap. bdr[]=<n> filters bedrooms.
            bedroom_counts = criteria.bedrooms_allowed or (criteria.bedrooms,)
            bdr = "".join(f"&bdr[]={n}" for n in bedroom_counts)
            ceiling = int(criteria.max_price_monthly_aed)
            edges = [0]
            first = min(6000, ceiling)
            if first > 0:
                edges.append(first)
            p = first
            while p < ceiling:
                p = min(p + 500, ceiling)
                edges.append(p)
            urls = []
            for lo, hi in zip(edges[:-1], edges[1:]):
                q = f"c=2&l=1&pt={hi * 12}"
                if lo > 0:
                    q += f"&pf={lo * 12}"
                urls.append(f"https://www.propertyfinder.ae/en/search?{q}{bdr}")
            # Coastal-Jumeirah supplement: the all-Dubai bands rarely capture the handful of
            # real Jumeirah flats in-budget (they're expensive and buried under thousands of
            # cheaper listings). When jumeirah_first is set, also query those communities
            # directly so they all show and can be floated to the top. Small (a page or two
            # each), fetched cheapest-first only.
            if getattr(criteria, "jumeirah_first", False):
                from ..config import COASTAL_JUMEIRAH_IDS
                pt_year = ceiling * 12
                jum_supplement_urls = [
                    f"https://www.propertyfinder.ae/en/search?c=2&l={cid}&pt={pt_year}{bdr}"
                    for cid in COASTAL_JUMEIRAH_IDS
                ]
        elif paths:
            urls = [f"https://www.propertyfinder.ae/en/rent/dubai/{p}" for p in paths]
        else:
            bedroom_counts = criteria.bedrooms_allowed or (criteria.bedrooms,)
            urls = [BASE_URL.format(slug=_bedroom_slug(n)) for n in bedroom_counts]
        orderings = getattr(criteria, "pf_orderings", ("pa",))
        max_pages = getattr(criteria, "pf_max_pages", MAX_PAGES)
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "en"}

        # (url, ob, page) work items — every bedroom search × sort order × page, concurrent.
        jobs = [(url, ob, page)
                for url in urls for ob in orderings for page in range(1, max_pages + 1)]
        # Jumeirah supplement: cheapest-first, just 2 pages each (these communities hold only
        # a handful of in-budget flats), added on top of the main jobs.
        jobs += [(url, "pa", page)
                 for url in jum_supplement_urls for page in (1, 2)]

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
    # Community id = path[1] of the location path (e.g. "1.66.1187.4520" → 66 = Jumeirah).
    # path[0] is the emirate (1 = Dubai). This pins the real community regardless of the
    # (often bare "Jumeirah") name text.
    community_id = None
    path = location.get("path") or ""
    parts = path.split(".")
    if len(parts) >= 2:
        try:
            community_id = int(parts[1])
        except (TypeError, ValueError):
            community_id = None

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
        community_id=community_id,
    )


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
