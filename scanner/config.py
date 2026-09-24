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
    # Accept ANY bedroom count (studio, 1..N, villas) — no bedroom restriction at all.
    any_bedrooms: bool = False
    # Literal Property Finder URL paths to fetch (e.g. "properties-for-rent.html" for ALL
    # property types — apartments, villas, townhouses, penthouses). When empty, the source
    # builds per-bedroom apartment URLs from the bedroom settings above instead.
    pf_property_paths: tuple[str, ...] = ()
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

    # Facebook Marketplace (Apify) tuning. fb_query is the search text sent to Marketplace
    # so it returns RELEVANT posts instead of the whole generic Dubai feed (which is why an
    # earlier version found 40 and matched none). None → the source builds a default from
    # the bedroom count. fb_results_limit caps how many cards it pulls per run.
    fb_query: str | None = None
    fb_results_limit: int = 100

    # Optional geographic bounding box (lat_min, lat_max, lon_min, lon_max). When set, a
    # listing WITH coordinates must fall inside it (listings without coordinates fall back
    # to the required_areas name match). This is how the Jumeirah tab is defined — by the
    # coastal strip on the map, not by area names — so look-alike names can't sneak in.
    bbox: tuple[float, float, float, float] | None = None

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

    # Extra hard-exclude terms matched against the AREA and the TITLE (like excluded_emirates
    # but for area look-alikes). Used by the Jumeirah tab to drop JBR and the inland
    # "Jumeirah Village/Park/Islands/…" areas even when they appear only in a freeform title.
    # Empty for the main search.
    excluded_terms: tuple[str, ...] = ()

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
        if self.any_bedrooms:
            return True
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
    # NO restrictions here beyond the location: this tab is "everything in the coastal
    # Jumeirah strip". No price cap (huge sentinel), every apartment size (studio → 5-bed),
    # and rooms too (via the Facebook button). The only filter is the map box + the JBR /
    # Marina / look-alike exclusions.
    max_price_monthly_aed=100_000_000,
    any_bedrooms=True,              # every size — studio, apartments, villas, penthouses
    allow_unknown_bedrooms=True,    # keep room/bed-space posts (no bedroom count)
    bathrooms=None,                 # don't require a bathroom count
    drop_room_shares=False,         # rooms / studios are explicitly wanted here
    # Fetch EVERY property type (apartments, villas, townhouses, penthouses), not just
    # apartments — the actual Jumeirah 1/2/3 district is mostly villas, so apartments-only
    # made the tab look Palm-heavy and "not all Jumeirah".
    pf_property_paths=("properties-for-rent.html",),
    # Both the pricey end (price-descending — most coastal stock is expensive Palm/Jumeirah)
    # and the cheap end, so the whole strip is covered at every price.
    pf_orderings=("pd", "pa"),
    pf_max_pages=20,  # 1 path × 2 orders × 20 = 40 page requests, fast; soft budget backs it
    check_freshness=False,          # show everything currently available, not just <30 days
    # The tab is defined by the MAP: the coastal strip from Jumeirah down past Al
    # Sufouh/Al Barsha to Palm, between the waterline and Sheikh Zayed Road (E11).
    # Calibrated from real listing coordinates — this cleanly includes Jumeirah 1/2/3,
    # Umm Suqeim, Al Wasl, City Walk, Al Sufouh, Al Barsha (coastal side) and Palm, while
    # excluding Marina/JBR (south of 25.09) and Downtown/Business Bay/Al Satwa (inland,
    # east of lon 55.255).
    bbox=(25.09, 25.235, 55.10, 55.255),
    # Name fallback for listings without coordinates (e.g. Facebook room posts):
    required_areas=(
        "jumeirah",
        "umm suqeim", "al sufouh", "al barsha", "madinat jumeirah",
        "la mer", "port de la mer", "pearl jumeirah",
        "city walk", "al wasl", "dubai canal",
        "palm jumeirah", "bluewaters",
    ),
    # Dropped even when they appear only in a freeform title: JBR (excluded per your ask),
    # Marina, and the inland areas that merely share the "Jumeirah" name.
    excluded_terms=(
        "jbr", "jumeirah beach residence",
        "dubai marina", "marina", "jlt", "jumeirah lake towers",
        "jumeirah village", "jumeirah park", "jumeirah islands",
        "jumeirah golf", "jumeirah heights",
        # Inland (city side of the coastal strip), so excluded per "along the coast":
        "al satwa", "jumeirah garden city",
    ),
    excluded_areas=(),  # handled by excluded_terms (area + title) above
)
