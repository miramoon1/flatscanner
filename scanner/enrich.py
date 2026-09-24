"""Shared enrichment: turn a Listing into the dashboard's data.json record.

One source of truth for the derived numbers (room-sublet estimate, net cost, EUR
conversion) so the local renderer (scanner/dashboard.py) and the Vercel serverless
scan (api/scan.py) always emit identical records.
"""
from __future__ import annotations

from .config import CRITERIA
from .filters import is_preferred_area
from .geocode import approx_coords
from .models import Listing
from .room_rent import estimate_room_rent

# AED is pegged to USD (~3.6725), but EUR/USD floats — so this rate drifts and should
# be refreshed periodically, unlike the AED figures (which come straight from listings).
# Confirmed live Sept 2026: 1 EUR = 4.2622 AED.
EUR_PER_AED = 1 / 4.2622


def _to_eur(aed: float | None) -> float | None:
    return aed * EUR_PER_AED if aed is not None else None


def enrich(listing: Listing, criteria=CRITERIA) -> dict:
    """Listing → dict with room-sublet estimate, net cost, and EUR conversions added."""
    room_typical, room_max = estimate_room_rent(listing.area)

    if listing.price_monthly_aed is not None:
        net_typical = listing.price_monthly_aed - room_typical
        net_best = listing.price_monthly_aed - room_max
    else:
        net_typical = net_best = None

    d = listing.to_dict()
    d["preferred"] = is_preferred_area(listing, criteria)
    d["profile"] = criteria.profile

    # Sources like Dubizzle/Facebook give an area name but no GPS. Place them on the map at
    # the community's approximate centre so they still get a pin (flagged as approximate).
    d["approx_location"] = False
    if d.get("latitude") is None or d.get("longitude") is None:
        lat, lon = approx_coords(listing.area)
        if lat is not None:
            d["latitude"], d["longitude"] = lat, lon
            d["approx_location"] = True
    d["est_room_rent_typical_aed"] = room_typical
    d["est_room_rent_max_aed"] = room_max
    d["net_cost_typical_aed"] = net_typical
    d["net_cost_best_case_aed"] = net_best
    d["est_room_rent_typical_eur"] = _to_eur(room_typical)
    d["est_room_rent_max_eur"] = _to_eur(room_max)
    d["net_cost_typical_eur"] = _to_eur(net_typical)
    d["net_cost_best_case_eur"] = _to_eur(net_best)
    return d
