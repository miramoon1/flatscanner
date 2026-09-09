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


# Sources with messy, freeform listings (Facebook Marketplace) rarely state bathroom
# count or a reliable date, and bedroom count is often only in the title. Applying the
# strict portal rules to them drops nearly everything. These sources get lenient rules:
# match on price + area + bedrooms, keep a listing when a field simply isn't stated
# (flagged "not listed" on the card), and skip the exact-bathroom and freshness checks.
LENIENT_SOURCES = {"facebook"}


def is_match(listing: Listing, criteria: Criteria) -> bool:
    lenient = listing.source in LENIENT_SOURCES

    # Excluded area is a hard no for everyone.
    if _area_matches_any(listing.area, criteria.excluded_areas):
        return False

    # Price: must be within budget when known. For lenient sources an unknown price is
    # kept (shown as "?"); for portals an unknown price is dropped.
    if listing.price_monthly_aed is not None:
        if listing.price_monthly_aed > criteria.max_price_monthly_aed:
            return False
    elif not lenient:
        return False

    # Bedrooms: exact match when known. Lenient sources keep unknown-bedroom listings.
    if listing.bedrooms is not None:
        if listing.bedrooms != criteria.bedrooms:
            return False
    elif not lenient:
        return False

    # Bathrooms + freshness: enforced only for the structured portal sources.
    if not lenient:
        if listing.bathrooms != criteria.bathrooms:
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
