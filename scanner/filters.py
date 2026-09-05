from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import Criteria
from .models import Listing

MAX_LISTING_AGE = timedelta(days=30)


def _area_matches_any(area: str, needles: tuple[str, ...]) -> bool:
    area_lower = (area or "").lower()
    return any(needle in area_lower for needle in needles)


def _is_too_old(listing: Listing) -> bool:
    """True only when the source told us a listed_at AND it's >30 days old.
    No listed_at (Bayut/Dubizzle don't reliably expose one from the search-results
    page — see their source modules) means we can't verify age, so we don't drop it;
    that would silently zero out sources that don't have a "posted date" available.
    """
    if not listing.listed_at:
        return False
    try:
        listed = datetime.fromisoformat(listing.listed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if listed.tzinfo is None:
        listed = listed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - listed > MAX_LISTING_AGE


def is_match(listing: Listing, criteria: Criteria) -> bool:
    if listing.price_monthly_aed is None or listing.price_monthly_aed > criteria.max_price_monthly_aed:
        return False
    if listing.bedrooms != criteria.bedrooms:
        return False
    if listing.bathrooms != criteria.bathrooms:
        return False
    if _area_matches_any(listing.area, criteria.excluded_areas):
        return False
    if _is_too_old(listing):
        return False
    return True


def is_preferred_area(listing: Listing, criteria: Criteria) -> bool:
    return _area_matches_any(listing.area, criteria.preferred_areas)


def filter_and_rank(listings: list[Listing], criteria: Criteria) -> list[Listing]:
    matches = [l for l in listings if is_match(l, criteria)]
    matches.sort(
        key=lambda l: (
            not is_preferred_area(l, criteria),  # preferred areas first
            l.price_monthly_aed if l.price_monthly_aed is not None else float("inf"),
        )
    )
    return matches
