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

BASE_URL = "https://www.propertyfinder.ae/en/rent/dubai/{bedrooms}-bedroom-apartments-for-rent.html"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
MAX_PAGES = 20
# Stop once we've seen this many consecutive listings priced well above budget
# (results are sorted price-ascending, so this means we've run past all matches).
OVERSHOOT_STREAK = 8


class PropertyFinderSource(Source):
    name = "propertyfinder"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})

        listings: list[Listing] = []
        overshoot = 0

        for page in range(1, MAX_PAGES + 1):
            url = BASE_URL.format(bedrooms=criteria.bedrooms)
            resp = session.get(url, params={"ob": "pa", "page": page}, timeout=20)
            if resp.status_code != 200:
                break

            props = _extract_properties(resp.text)
            if not props:
                break

            for prop in props:
                listing = _to_listing(prop)
                if listing is None:
                    continue
                listings.append(listing)

                if listing.price_monthly_aed is not None and listing.price_monthly_aed > criteria.max_price_monthly_aed * 1.5:
                    overshoot += 1
                else:
                    overshoot = 0

            if overshoot >= OVERSHOOT_STREAK:
                break

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
