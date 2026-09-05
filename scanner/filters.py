from __future__ import annotations

from .config import Criteria
from .models import Listing


def _area_matches_any(area: str, needles: tuple[str, ...]) -> bool:
    area_lower = (area or "").lower()
    return any(needle in area_lower for needle in needles)


def is_match(listing: Listing, criteria: Criteria) -> bool:
    if listing.price_monthly_aed is None or listing.price_monthly_aed > criteria.max_price_monthly_aed:
        return False
    if listing.bedrooms != criteria.bedrooms:
        return False
    if listing.bathrooms != criteria.bathrooms:
        return False
    if _area_matches_any(listing.area, criteria.excluded_areas):
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
