"""Dubizzle via Apify — the Vercel-compatible way to scrape Dubizzle (no local browser).

Same rationale and caveats as bayut_apify.py: Dubizzle sits behind Imperva Incapsula, so
it needs a real browser, which Vercel can't run — Apify runs it remotely instead. OPT-IN:
runs only when APIFY_DUBIZZLE_ACTOR names an actor (e.g. "datafusion_x/dubizzle-property-scraper-uae").
Third-party/paid, output unverified here → defensive parsing, per-listing failures
swallowed. Diff against a real Apify Console run if it comes back empty.
"""
from __future__ import annotations

import os

import requests

from ..config import Criteria
from ..models import Listing
from . import Source


class DubizzleApifySource(Source):
    name = "dubizzle"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        token = os.environ.get("APIFY_API_TOKEN")
        actor = os.environ.get("APIFY_DUBIZZLE_ACTOR")
        if not token or not actor:
            return []

        # The cheapest usable Dubizzle actor (easyapi/dubizzle-list-search-scraper,
        # ~$2.99/1000) takes a Dubizzle *search URL*, not filter fields. Set
        # APIFY_DUBIZZLE_SEARCH_URL to the exact filtered URL from your browser (filter
        # dubizzle to 2-bed apartments for rent in Dubai, copy the address bar) for best
        # results; otherwise it falls back to the general apartments-for-rent search and
        # our own filters (price/beds/baths/area) narrow it down. Filter-style keys are
        # sent too so filter-based actors also work — extra keys are ignored.
        search_url = os.environ.get(
            "APIFY_DUBIZZLE_SEARCH_URL",
            "https://dubai.dubizzle.com/property-for-rent/residential/apartments/",
        )
        api_url = f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"
        resp = requests.post(
            api_url,
            params={"token": token},
            json={
                "searchUrl": search_url,
                "maxResults": 200,
                "city": "dubai",
                "category": "property-for-rent",
                "subCategory": "apartments",
                "bedrooms": criteria.bedrooms,
                "maxPrice": criteria.max_price_monthly_aed * 12,  # yearly quotes common
                "maxItems": 200,
            },
            timeout=300,
        )
        resp.raise_for_status()
        return [l for l in (_to_listing(i) for i in resp.json()) if l is not None]


def _first(item: dict, *keys):
    for k in keys:
        v = item.get(k)
        if v not in (None, ""):
            return v
    return None


def _to_listing(item: dict) -> Listing | None:
    try:
        url = _first(item, "url", "listingUrl", "permalink", "shareUrl")
        if not url:
            return None
        if not str(url).startswith("http"):
            url = f"https://dubai.dubizzle.com{url}"

        price_monthly = _price_to_monthly(_first(item, "price", "priceValue", "rent"), item)

        area = _first(item, "location", "neighbourhood", "area", "locationName") or ""
        if isinstance(area, list):
            area = ", ".join(str(a.get("name", a) if isinstance(a, dict) else a) for a in area)

        coords = _first(item, "coordinates", "geo", "location_coordinates") or {}
        lat = coords.get("lat") if isinstance(coords, dict) else None
        lon = (coords.get("lng") or coords.get("lon")) if isinstance(coords, dict) else None

        photos = _first(item, "photos", "images", "coverPhoto")
        image_url = None
        if isinstance(photos, str):
            image_url = photos
        elif isinstance(photos, list) and photos:
            image_url = photos[0].get("url") if isinstance(photos[0], dict) else photos[0]
        elif isinstance(photos, dict):
            image_url = photos.get("url")

        return Listing(
            source="dubizzle",
            source_id=str(_first(item, "id", "listingId", "externalID") or url),
            title=_first(item, "title", "name") or "",
            url=str(url),
            price_monthly_aed=price_monthly,
            bedrooms=_to_int(_first(item, "bedrooms", "rooms", "beds")),
            bathrooms=_to_int(_first(item, "bathrooms", "baths")),
            area=str(area),
            image_url=image_url,
            listed_at=_first(item, "createdAt", "listedAt", "postedAt"),
            latitude=lat,
            longitude=lon,
        )
    except Exception:
        return None


def _price_to_monthly(price, item: dict) -> float | None:
    try:
        value = float(str(price).replace(",", "")) if price is not None else None
    except (TypeError, ValueError):
        value = None
    if value is None:
        return None
    period = str(_first(item, "frequency", "rentFrequency", "period", "priceType") or "").lower()
    if "month" in period:
        return value
    if "week" in period:
        return value * 52 / 12
    if "day" in period:
        return value * 365 / 12
    if "year" in period or "annual" in period:
        return value / 12
    # Dubizzle rooms/short-term are often monthly; flats often yearly. When unstated,
    # assume yearly for a plausible apartment rent (a value in the tens of thousands
    # would otherwise read as an absurd monthly figure).
    return value / 12 if value > 20000 else value


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
