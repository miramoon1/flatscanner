"""Search criteria for the flat scanner. Edit this file to change what counts as a match."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Criteria:
    max_price_monthly_aed: int = 6000
    bedrooms: int = 2
    bathrooms: int | None = 2  # None = don't require any specific bathroom count

    # When set, a listing matches if its bedroom count is in this set (e.g. a studio/1-bed
    # search uses (0, 1)). When None, the single `bedrooms` value above is required exactly.
    # Lets a second search profile (Jumeirah studio/1BR) reuse the same filter code.
    bedrooms_allowed: tuple[int, ...] | None = None
    # Keep a listing whose bedroom count couldn't be determined (some freeform posts).
    allow_unknown_bedrooms: bool = False
    # Positive area allow-list (matched against area AND title). Empty = no restriction —
    # any area that isn't excluded is allowed. When set, a listing must name one of these.
    required_areas: tuple[str, ...] = ()
    # Drop room-share / partition / studio posts on freeform sources. Off for a profile
    # that actually wants rooms/studios (the Jumeirah tab).
    drop_room_shares: bool = True
    # Enforce the "listed within 30 days" recency rule (portals only). The main search
    # wants fresh listings; the Jumeirah browse tab wants everything currently available.
    check_freshness: bool = True

    # Property Finder fetch tuning. `pf_orderings` is the list of `ob=` sort orders to
    # pull ("pa" = price ascending, "pd" = price descending). The main scan only needs the
    # cheap end ("pa"); an area-restricted profile also pulls "pd" so it captures the
    # pricier (but area-relevant) listings that never appear in the cheapest pages.
    pf_orderings: tuple[str, ...] = ("pa",)
    pf_max_pages: int = 16

    # A short human label + id for the search profile (used by the dashboard tabs / colors).
    profile: str = "main"

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


# Second search profile: a studio / 1-bedroom (or a room) anywhere on the DUBAI coastal
# Jumeirah strip — Jumeirah 1/2/3, Umm Suqeim, Al Sufouh, La Mer, Pearl Jumeirah, City
# Walk, Palm, Bluewaters — but NOT JBR, NOT Dubai Marina, and NOT the inland "Jumeirah
# Village/Park/Islands/Lake Towers" areas (which merely share the Jumeirah name). Coastal
# Jumeirah runs pricey, so the cap is higher than the main 2-bed budget. required_areas is
# a positive allow-list: a listing must name one of these coastal areas to show here.
JUMEIRAH_CRITERIA = Criteria(
    profile="jumeirah",
    # Hard budget: same 6,000 AED/month ceiling as the main search. Coastal Jumeirah runs
    # pricey, so studio/1-bed under this cap is genuinely scarce — the tab shows what
    # actually exists in budget, cheapest first, rather than pretending there's more.
    max_price_monthly_aed=6000,
    bedrooms_allowed=(0, 1),        # studio + 1-bed
    bathrooms=None,                 # don't require a bathroom count for a studio/1BR
    drop_room_shares=False,         # "a room" is explicitly wanted here
    # Cheapest-first only (a price-descending pass would just fetch listings above the cap)
    # and page fairly deep, since affordable coastal Jumeirah units are sparse.
    pf_orderings=("pa",),
    pf_max_pages=25,
    check_freshness=False,          # show everything currently available, not just <30 days
    required_areas=(
        "jumeirah 1", "jumeirah 2", "jumeirah 3", "jumeirah 4",
        "umm suqeim", "al sufouh", "la mer", "port de la mer",
        "pearl jumeirah", "jumeirah bay", "city walk", "al wasl",
        "palm jumeirah", "bluewaters",
    ),
    # Exclude look-alikes that share the "Jumeirah" name but aren't the coastal strip,
    # plus JBR/Marina. (excluded_emirates keeps its default — other emirates stay out.)
    excluded_areas=(
        "dubai marina", "marina", "jlt", "jumeirah lake towers",
        "jumeirah beach residence", "jbr",
        "jumeirah village", "jumeirah park", "jumeirah islands",
        "jumeirah golf", "jumeirah heights",
    ),
)
