"""Facebook Marketplace via Apify — the recommended way to get Marketplace data.

Runs the OFFICIAL `apify/facebook-marketplace-scraper` actor on Apify's own
infrastructure. This is the reason it's worth using over scanner/sources/facebook.py
(the Playwright + your-own-login version, kept only as a documented fallback):
**your Facebook account is never involved** — no login, no cookies, no ban exposure to
your account. Apify hits Marketplace with their own infra and hands back structured
listings; whatever risk that carries is theirs, not yours.

Confirmed live (Sept 2026) via web search, not guesswork: Facebook Marketplace uses a
numeric place ID per city, not a name slug — "https://www.facebook.com/marketplace/dubai/..."
(what an earlier version of this project guessed) is WRONG. Dubai's real ID is
111070818917271, giving:
    https://www.facebook.com/marketplace/111070818917271/propertyrentals/

Setup:
    1. Sign up at apify.com (free tier: $5/month usage credit, ~1000 listings/month —
       plenty for a once-a-day check).
    2. Get your API token: Apify Console → Settings → Integrations.
    3. Set it as the APIFY_API_TOKEN environment variable (locally, or as a GitHub
       Actions repo secret for the scheduled workflow).

Marketplace doesn't expose separate bedroom/bathroom fields the way property portals
do, so — same as the login-based facebook.py — we regex bed/bath counts out of the
listing title/description and drop anything that doesn't state both, rather than
guess. The exact field names in `_to_listing` below are written defensively (multiple
candidate keys tried per field) because this actor's dataset schema wasn't independently
verified end-to-end in this project's environment (no Apify token was available to test
with) — if it comes back empty, run the actor once from the Apify Console with the URL
above and diff the real output against `_to_listing`.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests

from ..config import Criteria
from ..models import Listing
from . import Source

ACTOR_ID = "apify/facebook-marketplace-scraper"
DUBAI_PROPERTY_RENTALS_URL = "https://www.facebook.com/marketplace/111070818917271/propertyrentals/"
API_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"

BEDS_RE = re.compile(r"(\d+)\s*(?:bed|br|bhk)", re.I)
BATHS_RE = re.compile(r"(\d+)\s*(?:bath|ba)\b", re.I)


class FacebookApifySource(Source):
    name = "facebook"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        token = os.environ.get("APIFY_API_TOKEN")
        if not token:
            # Raise (rather than return []) so this surfaces in /api/data's `sources`
            # block as a clear, actionable error instead of Facebook silently vanishing.
            raise RuntimeError(
                "APIFY_API_TOKEN is not set in this environment — add it in Vercel "
                "(Project → Settings → Environment Variables), then redeploy."
            )

        resp = requests.post(
            API_URL,
            params={"token": token},
            json={
                "startUrls": [{"url": DUBAI_PROPERTY_RENTALS_URL}],
                "resultsLimit": 200,
                "includeListingDetails": True,
            },
            timeout=180,
        )
        resp.raise_for_status()
        items = resp.json()

        listings = []
        for item in items:
            listing = _to_listing(item, criteria)
            if listing is not None:
                listings.append(listing)
        return listings


def _to_listing(item: dict, criteria: Criteria) -> Listing | None:
    url = item.get("itemUrl") or item.get("url") or item.get("listingUrl")
    if not url:
        return None

    title = item.get("listingTitle") or item.get("title") or item.get("marketplace_listing_title") or ""
    description = item.get("description") or item.get("listingDescription") or ""
    text = f"{title} {description}"

    beds_match = BEDS_RE.search(text)
    baths_match = BATHS_RE.search(text)
    if not beds_match or not baths_match:
        return None  # can't verify bed/bath count from the listing text, skip rather than guess

    price_monthly = _extract_price_monthly(item, text)

    # "location" can come back as a plain string OR a nested {text, latitude,
    # longitude} object depending on the actor version — handle both rather than
    # assume, since assigning a dict straight into area (a string field) would be wrong.
    raw_location = item.get("location")
    nested_location = raw_location if isinstance(raw_location, dict) else {}
    area = item.get("locationText") or nested_location.get("text") or (raw_location if isinstance(raw_location, str) else "") or ""

    photos = item.get("listingPhotos") or item.get("images") or []
    image_url = photos[0] if photos and isinstance(photos[0], str) else None

    source_id = str(item.get("id") or url.rstrip("/").rsplit("/", 1)[-1])

    listed_at = item.get("creationTime") or item.get("creation_time") or item.get("listingCreationTime")
    if isinstance(listed_at, (int, float)):
        # Some Apify FB actors report this as a unix timestamp rather than ISO text.
        listed_at = datetime.fromtimestamp(listed_at, tz=timezone.utc).isoformat()

    latitude = item.get("latitude") or nested_location.get("latitude")
    longitude = item.get("longitude") or nested_location.get("longitude")

    return Listing(
        source="facebook",
        source_id=source_id,
        title=title or text[:80],
        url=url,
        price_monthly_aed=price_monthly,
        bedrooms=int(beds_match.group(1)),
        bathrooms=int(baths_match.group(1)),
        area=area,
        image_url=image_url,
        listed_at=listed_at if isinstance(listed_at, str) else None,
        latitude=latitude,
        longitude=longitude,
    )


def _extract_price_monthly(item: dict, text: str) -> float | None:
    price = item.get("listingPrice") or item.get("price")
    value = None
    if isinstance(price, dict):
        value = price.get("amount") or price.get("value")
    elif isinstance(price, (int, float)):
        value = price
    elif isinstance(price, str):
        digits = "".join(ch for ch in price if ch.isdigit())
        value = float(digits) if digits else None

    if value is None:
        match = re.search(r"AED\s*([\d,]+)", text, re.I)
        value = float(match.group(1).replace(",", "")) if match else None

    if value is None:
        return None

    value = float(value)
    if re.search(r"/\s*year|yearly|per year", text, re.I):
        return value / 12
    return value  # Marketplace rentals are conventionally listed per-month
