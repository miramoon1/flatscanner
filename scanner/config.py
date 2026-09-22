"""Search criteria for the flat scanner. Edit this file to change what counts as a match."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Criteria:
    max_price_monthly_aed: int = 6000
    bedrooms: int = 2
    bathrooms: int = 2

    # When set, a listing matches if its bedroom count is in this set (e.g. a studio/1-bed
    # search uses (0, 1)). When None, the single `bedrooms` value above is required exactly.
    # Lets a second search profile (Jumeirah studio/1BR) reuse the same filter code.
    bedrooms_allowed: tuple[int, ...] | None = None

    # Dubai sub-areas you don't want. Matched against the listing's AREA field only, not
    # its title: a genuine JBR/Bluewaters listing often says "near Dubai Marina" in its
    # freeform title, and matching that would wrongly drop it. (Substring, lower-cased.)
    excluded_areas: tuple[str, ...] = (
        "dubai marina",
        "marina",
        "jlt",
        "jumeirah lake towers",
    )

    # Other emirates — you only want Dubai. Facebook's "Dubai property rentals" feed (and
    # any radius-based search) leaks in listings from neighbouring emirates, and the
    # emirate is frequently stated ONLY in a freeform title ("2BHK for rent in Ajman"),
    # with the structured area field left blank or mislabelled. So these are matched
    # against the AREA field AND the TITLE, and anything naming another emirate is
    # dropped. "umm al quwain" won't clash with the preferred Dubai area "umm suqeim".
    excluded_emirates: tuple[str, ...] = (
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

    def bedroom_ok(self, n: int) -> bool:
        """True if a listing's bedroom count satisfies this profile."""
        if self.bedrooms_allowed is not None:
            return n in self.bedrooms_allowed
        return n == self.bedrooms


CRITERIA = Criteria()
