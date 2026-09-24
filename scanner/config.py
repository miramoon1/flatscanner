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
    # Property Finder LOCATION community ids to filter to (via its /en/search?c=2&l=<id>
    # route — the real location filter). When set, the source queries each community
    # directly, so results are exactly those areas at every price point. This is how the
    # Jumeirah tab gets accurate, complete coverage instead of guessing by name/box.
    pf_location_ids: tuple[int, ...] = ()
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
    # This tab is "everything in the real coastal Jumeirah strip". No price cap (huge
    # sentinel), every apartment size (studio → 3-bed, plus unknown), and rooms too
    # (via the Facebook button).
    max_price_monthly_aed=100_000_000,   # no cap; sorted cheapest-first so cheap shows first
    bedrooms_allowed=(0, 1, 2, 3),  # studio, 1/2/3-bed flats — the affordable end
    allow_unknown_bedrooms=True,    # keep studios (no bed count) + room posts
    bathrooms=None,                 # don't require a bathroom count
    drop_room_shares=False,         # rooms / studios are explicitly wanted here
    # THE fix for "things that are truly not Jumeirah" + "2bhk that don't show": Property
    # Finder's REAL location filter — /en/search?c=2&l=<community_id>. The old bedroom-slug +
    # map-box approach pulled all of Dubai and clipped by pin, which leaked Al Barsha/Al Quoz
    # and dropped listings whose pin sat just off the box. This returns EXACTLY these
    # communities server-side, at every price band, cheapest-first. Community ids are the
    # path[1] of each listing's location path, coastal Jumeirah only:
    #   66 = Jumeirah (1/2/3)   86 = Palm Jumeirah   98 = Umm Suqeim
    #   30 = Al Sufouh          33 = Al Wasl         9529 = City Walk   9042 = Bluewaters
    # Verified live: 1,750 real-Jumeirah rent listings across the full range, cheapest
    # ~3,750/mo, no Al Barsha / Marina / JVC noise.
    pf_location_ids=(66, 86, 98, 30, 33, 9529, 9042),
    pf_orderings=("pa",),
    pf_max_pages=6,    # 7 communities × 6 pages ≈ 42 requests, cheapest-first; soft budget caps time
    # The paid Facebook button on this tab searches Marketplace for ROOMS (Property Finder
    # has no rooms). Facebook posts can't be location-filtered, so the area-name gate below
    # (required_areas / excluded_terms) is what keeps them inside coastal Jumeirah.
    fb_query="room for rent",
    check_freshness=False,          # show everything currently available, not just <30 days
    # No coordinate box: the PF location filter is already precise, and the box was clipping
    # good listings whose pin sat just outside it. Facebook/Dubizzle (no pin) fall back to
    # this area-name allow-list, which mirrors the community ids above (no Al Barsha).
    bbox=None,
    required_areas=(
        "jumeirah",
        "umm suqeim", "al sufouh", "madinat jumeirah",
        "la mer", "port de la mer", "pearl jumeirah",
        "city walk", "al wasl", "dubai canal",
        "palm jumeirah", "bluewaters",
    ),
    # Dropped even when they appear only in a freeform title (protects the Facebook path):
    # JBR, Marina, the inland look-alikes that merely share the "Jumeirah" name, and the
    # inland city-side areas that were leaking in before.
    excluded_terms=(
        "jbr", "jumeirah beach residence",
        "dubai marina", "marina", "jlt", "jumeirah lake towers",
        "jumeirah village", "jumeirah park", "jumeirah islands",
        "jumeirah golf", "jumeirah heights",
        "al satwa", "jumeirah garden city",
        "al barsha", "al quoz",
    ),
    excluded_areas=(),  # handled by excluded_terms (area + title) above
)
