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


# Freeform sources (Facebook Marketplace, Dubizzle-via-Apify) don't reliably expose a
# bathroom count or a posted date, so those two checks are skipped for them. But EVERY
# other check still applies at full strength — crucially, price and bedrooms must be
# KNOWN and must match. Keeping unknown-price / unknown-bedroom listings (an earlier,
# over-lenient version did) is exactly what turned Facebook into a firehose of random
# junk, so we don't: a post that doesn't clearly state a matching price and bedroom count
# isn't a usable result and is dropped.
#   - facebook: bed count is parsed from the freeform title; no title match → dropped.
#   - dubizzle (via Apify): the cheap actor's output has no bathrooms field / posted date.
LENIENT_SOURCES = {"facebook", "dubizzle"}

# Lenient (freeform) sources are full of room-share posts that aren't whole 2-bed flats —
# "partition", "bed space", studio, etc. These have no bedroom count to filter on, so drop
# them by keyword. Only applied to lenient sources; portals never carry these.
NON_FLAT_TERMS = ("partition", "bed space", "bedspace", "shared room", "sharing", "studio")


def is_match(listing: Listing, criteria: Criteria) -> bool:
    lenient = listing.source in LENIENT_SOURCES

    area = listing.area or ""
    title = listing.title or ""
    area_and_title = f"{area} {title}"

    # Dubai sub-areas (Marina/JLT): match the area field only — see config.excluded_areas.
    if _area_matches_any(area, criteria.excluded_areas):
        return False
    # Other emirates (Ajman/Sharjah/…): match area AND title, because freeform sources
    # (Facebook especially) put the emirate in the title with a blank area field. This is
    # what let Ajman/Sharjah listings slip through before.
    if _area_matches_any(area_and_title, criteria.excluded_emirates):
        return False

    # Extra area look-alike exclusions (JBR, inland "Jumeirah *" areas) — area AND title.
    if _area_matches_any(area_and_title, criteria.excluded_terms):
        return False

    # Positive area allow-list (e.g. the Jumeirah tab): when set, the listing must name one
    # of the required areas (checked against area AND title).
    if criteria.required_areas and not _area_matches_any(area_and_title, criteria.required_areas):
        return False

    # Room-share / partition / studio posts on freeform sources: not a whole flat — dropped
    # unless the profile explicitly wants rooms/studios (drop_room_shares=False).
    if lenient and criteria.drop_room_shares and _area_matches_any(area_and_title, NON_FLAT_TERMS):
        return False

    # Price: required and within budget for ALL sources (including lenient ones). An
    # unknown price means we can't tell if it fits the budget, so it's not a usable result.
    if listing.price_monthly_aed is None or listing.price_monthly_aed > criteria.max_price_monthly_aed:
        return False

    # Bedrooms: a known count must be allowed by the profile; an unknown count is dropped
    # unless the profile keeps unknown-bedroom listings.
    if listing.bedrooms is None:
        if not criteria.allow_unknown_bedrooms:
            return False
    elif not criteria.bedroom_ok(listing.bedrooms):
        return False

    # Bathrooms + freshness: enforced only for the structured portal sources.
    if not lenient:
        if criteria.bathrooms is not None and listing.bathrooms != criteria.bathrooms:
            return False
        if criteria.check_freshness and _is_too_old(listing):
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
