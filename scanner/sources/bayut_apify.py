"""Bayut via Apify — the Vercel-compatible way to scrape Bayut (no local browser).

Bayut sits behind a bot-management JS challenge, so it needs a real browser. On Vercel
(serverless, no browser) the only way to keep Bayut is to run it on Apify's infra, the
same pattern as Facebook. This is OPT-IN: it only runs when APIFY_BAYUT_ACTOR names an
actor (e.g. "therealdude/bayut-uae-scraper"), because those are third-party, mostly paid
actors whose exact output this project couldn't verify end-to-end (no Apify token was
available to test with). Parsing below is deliberately defensive — multiple candidate
keys per field — and any failure is swallowed per-listing so a schema mismatch skips a
card instead of breaking the run. If it returns nothing once deployed, run the actor
once from the Apify Console and diff its real output against `_to_listing`.
"""
from __future__ import annotations

import os

import requests

from ..config import Criteria
from ..models import Listing
from . import Source


class BayutApifySource(Source):
    name = "bayut"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        token = os.environ.get("APIFY_API_TOKEN")
        actor = os.environ.get("APIFY_BAYUT_ACTOR")
        if not token or not actor:
            return []

        api_url = f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"
        resp = requests.post(
            api_url,
            params={"token": token},
            json={
                # Generic input shape; actors vary — this targets Dubai apartment rentals.
                "location": "dubai",
                "purpose": "for-rent",
                "propertyType": "apartments",
                "rooms": criteria.bedrooms,
                "maxPrice": criteria.max_price_monthly_aed * 12,  # Bayut quotes yearly
                "maxItems": 200,
            },
            timeout=40,
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
        url = _first(item, "url", "externalID", "shareUrl", "permalink")
        if not url:
            return None
        if not str(url).startswith("http"):
            url = f"https://www.bayut.com/property/details-{url}.html"

        price = _first(item, "price", "priceValue", "rent")
        price_monthly = _price_to_monthly(price, item)

        area = _first(item, "location", "locationName", "areaName", "community") or ""
        if isinstance(area, list):
            area = ", ".join(str(a.get("name", a) if isinstance(a, dict) else a) for a in area)

        coords = _first(item, "geography", "coordinates", "geo") or {}
        lat = coords.get("lat") if isinstance(coords, dict) else None
        lon = coords.get("lng") if isinstance(coords, dict) else (coords.get("lon") if isinstance(coords, dict) else None)

        photos = _first(item, "coverPhoto", "photos", "images", "coverPhotoURL")
        image_url = None
        if isinstance(photos, str):
            image_url = photos
        elif isinstance(photos, dict):
            image_url = photos.get("url")
        elif isinstance(photos, list) and photos:
            image_url = photos[0].get("url") if isinstance(photos[0], dict) else photos[0]

        return Listing(
            source="bayut",
            source_id=str(_first(item, "id", "externalID") or url),
            title=_first(item, "title", "name") or "",
            url=str(url),
            price_monthly_aed=price_monthly,
            bedrooms=_to_int(_first(item, "rooms", "bedrooms", "beds")),
            bathrooms=_to_int(_first(item, "baths", "bathrooms")),
            area=str(area),
            image_url=image_url,
            listed_at=_first(item, "createdAt", "listedAt", "reactivatedAt"),
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
    period = str(_first(item, "rentFrequency", "priceType", "period") or "").lower()
    if "month" in period:
        return value
    if "week" in period:
        return value * 52 / 12
    if "day" in period:
        return value * 365 / 12
    return value / 12  # Bayut default is yearly


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
