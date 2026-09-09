"""Search criteria for the flat scanner. Edit this file to change what counts as a match."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Criteria:
    max_price_monthly_aed: int = 6000
    bedrooms: int = 2
    bathrooms: int = 2

    # Listings in these areas are hard-excluded even if everything else matches — for
    # every source, Facebook included. Two groups:
    #   1. Dubai sub-areas you don't want (Marina, JLT).
    #   2. Other emirates — Facebook's "Dubai property rentals" feed leaks in listings
    #      from neighbouring emirates (Sharjah, Ajman, etc.); you only want Dubai, so
    #      anything naming another emirate is dropped. (Substring match, lower-cased.)
    #      "umm al quwain" won't clash with the preferred Dubai area "umm suqeim".
    excluded_areas: tuple[str, ...] = (
        "dubai marina",
        "marina",
        "jlt",
        "jumeirah lake towers",
        "sharjah",
        "ajman",
        "umm al quwain",
        "ras al khaimah",
        "fujairah",
        "abu dhabi",
        "al ain",
    )

    # Listings in these areas are flagged "preferred" on the dashboard and sorted first.
    # This is a *preference*, not a filter — matching listings outside this list still show up,
    # as long as they clear the excluded_areas check above.
    #
    # Deliberately NOT including a bare "jumeirah" entry: Dubai has several
    # "Jumeirah *"-branded areas that aren't actually the water-adjacent Jumeirah
    # district — Jumeirah Village Circle/Triangle, Jumeirah Lake Towers, Jumeirah Park,
    # Jumeirah Heights — and a plain substring match on "jumeirah" was silently
    # matching all of them too (confirmed live: "Jumeirah Village Circle, Dubai" was
    # getting flagged "Preferred area"). The specific entries below (Jumeirah 1/2/3,
    # JBR, Palm Jumeirah, Jumeirah Golf Estates, etc.) already cover every genuine
    # Jumeirah-area listing seen in real data without that false-positive risk.
    preferred_areas: tuple[str, ...] = (
        "jumeirah 1",
        "jumeirah 2",
        "jumeirah 3",
        "jbr",
        "jumeirah beach residence",
        "palm jumeirah",
        "la mer",
        "bluewaters",
        "jumeirah islands",
        "city walk",
        "al sufouh",
        "umm suqeim",
        "port de la mer",
        "jumeirah golf estates",
    )


CRITERIA = Criteria()
