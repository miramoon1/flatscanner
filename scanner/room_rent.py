"""Estimated private-room rental rates, by Dubai area, for winter (peak) season.

Used to answer "if I sublet the second bedroom, what would I actually be paying
net?" — this is NOT scraped live data. Dubai's room/shared-accommodation listings
(Dubizzle's "Rooms for rent" category, mainly) sit behind Imperva Incapsula, the same
bot-management wall documented in scanner/sources/dubizzle.py, and it blocked this
project's attempts to pull live room-rental listings the same way it blocks the flat
listings. So instead of guessing, these are tiered estimates built from published
market ranges (real-estate blogs, relocation guides, shared-accommodation platforms —
see README for the specific figures and sources) for CURRENT/winter-season asking
prices, grouped into three tiers by area desirability. Treat these as a ballpark for
budgeting, not a quote — the actual rate for a specific room depends heavily on
furnishing, exact building, and who you're renting to.

"Winter" here means Nov–Mar, Dubai's peak season for both tourism and expat
relocation — room demand (and asking prices) run higher than in summer. No UAE-specific
numeric seasonal multiplier for MONTHLY room shares turned up in research (only for
nightly hotel rates, which move far more and don't transfer to a monthly rental
market) — so the ranges below are the researched figures themselves, already
representing current/peak-season asking prices rather than a discounted summer rate.
"""
from __future__ import annotations

from .config import CRITERIA

# (typical, max) AED/month, winter/peak-season asking price for a private room.
BUDGET_TIER = (2200.0, 3500.0)
MID_TIER = (3200.0, 4500.0)
PREMIUM_TIER = (4800.0, 7000.0)

BUDGET_AREA_KEYWORDS = (
    "deira",
    "bur dubai",
    "al nahda",
    "international city",
    "muhaisnah",
    "al warqa",
    "al qusais",
    "discovery gardens",
    "al quoz",
)

# Premium tier reuses the same "preferred" (Jumeirah / water-adjacent) area list
# already defined for the main scanner criteria — one source of truth for what
# counts as a desirable area, instead of a second list that could drift out of sync.
PREMIUM_AREA_KEYWORDS = CRITERIA.preferred_areas + ("downtown", "business bay")


def estimate_room_rent(area: str) -> tuple[float, float]:
    """Return (typical, max) AED/month for a private room in this area, winter rate."""
    area_lower = (area or "").lower()
    if any(kw in area_lower for kw in PREMIUM_AREA_KEYWORDS):
        return PREMIUM_TIER
    if any(kw in area_lower for kw in BUDGET_AREA_KEYWORDS):
        return BUDGET_TIER
    return MID_TIER
