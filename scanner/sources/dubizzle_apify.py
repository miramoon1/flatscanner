"""Dubizzle via Apify — the Vercel-compatible way to scrape Dubizzle (no local browser).

Dubizzle sits behind Imperva Incapsula, so it needs a real browser, which Vercel can't
run — and a free cloud browser (GitHub Actions) gets bot-blocked outright (confirmed: the
runner is served an Incapsula challenge stub, zero listings). Apify runs it from
infrastructure that gets through, for a small per-result fee.

OPT-IN and paid: runs only when APIFY_DUBIZZLE_ACTOR names an actor, and only on the
dashboard's explicit "paid sources" button. Recommended actor (cheapest verified,
$1.50/1000 results, structured filters, Sept 2026):

    APIFY_DUBIZZLE_ACTOR = logiover/dubizzle-scraper

Its input is structured (section/emirate/bedsMin/priceMax/sortBy/maxResults) and its
output has no bathrooms field, no posted date and no coordinates — hence Dubizzle is a
"lenient" source in scanner/filters.py (matched on price + area + bedrooms). We send a
superset of input keys so a differently-shaped actor still gets what it needs; unknown
keys are ignored. Parsing is defensive (multiple candidate keys per field). If it comes
back empty, run the actor once in the Apify Console and diff its output against
`_to_listing`.
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
        actor = os.environ.get("APIFY_DUBIZZLE_ACTOR")
        if not actor:
            return []  # opt-in: not configured, stay silent
        token = os.environ.get("APIFY_API_TOKEN")
        if not token:
            raise RuntimeError(
                "APIFY_DUBIZZLE_ACTOR is set but APIFY_API_TOKEN is missing — add the "
                "token in Vercel (Project → Settings → Environment Variables), then redeploy."
            )

        # Yearly cap: Dubizzle rents are usually quoted per year, so bound the actor-side
        # price filter at the monthly budget × 12. Cheap monthly-quoted listings are well
        # under this too, so none are lost; our own filter re-checks the true monthly price.
        yearly_cap = criteria.max_price_monthly_aed * 12
        # A URL fallback for actors that take a search URL instead of structured filters.
        search_url = os.environ.get(
            "APIFY_DUBIZZLE_SEARCH_URL",
            "https://dubai.dubizzle.com/property-for-rent/residential/apartments/",
        )
        api_url = f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"
        resp = requests.post(
            api_url,
            params={"token": token},
            json={
                # logiover/dubizzle-scraper (recommended) — structured Algolia filters:
                "section": "property-for-rent",
                "emirate": "dubai",
                "propertyCategory": "residential",
                "bedsMin": criteria.bedrooms,   # actor has no exact/max beds; we filter exact after
                "priceMax": yearly_cap,
                "sortBy": "newest",             # no posted-date field, so lean on newest-first
                "maxResults": 200,
                # Harmless extras so URL-based actors also work (unknown keys are ignored):
                "url": search_url,
                "max_result": 200,
                "maxItems": 200,
            },
            timeout=50,
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
