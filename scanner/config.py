"""Search criteria for the flat scanner. Edit this file to change what counts as a match."""
from __future__ import annotations

from dataclasses import dataclass, field

# The REAL coastal Jumeirah, as Property Finder community ids (path[1] of a listing's
# location path). This is the single source of truth for "Jumeirah" per the user's
# definition — the coastal strip between the sea and Sheikh Zayed Road — and is used both
# to drive the Jumeirah tab (pf_location_ids) and to float these listings to the top of
# the main Flatshare tab. Ids: 66 Jumeirah 1/2/3, 86 Palm, 98 Umm Suqeim, 30 Al Sufouh,
# 33 Al Wasl, 9529 City Walk, 9042 Bluewaters. Deliberately NOT Jumeirah Village/Park/
# Islands/Golf/Heights, JBR, Marina, Al Barsha — those are inland or non-Jumeirah.
COASTAL_JUMEIRAH_IDS = (66, 86, 98, 30, 33, 9529, 9042)
# Name fallback for sources without a community id (Facebook/Dubizzle). Precise terms only
# — no bare "jumeirah" (it matches Jumeirah Village etc.).
COASTAL_JUMEIRAH_NAMES = (
    "jumeirah 1", "jumeirah 2", "jumeirah 3",
    "umm suqeim", "al sufouh", "al wasl", "madinat jumeirah",
    "la mer", "port de la mer", "pearl jumeirah",
    "city walk", "palm jumeirah", "bluewaters",
)
COASTAL_JUMEIRAH_LOOKALIKES = (
    "jumeirah village", "jumeirah park", "jumeirah islands",
    "jumeirah golf", "jumeirah heights", "jbr", "jumeirah beach residence",
    "jlt", "jumeirah lake towers", "al barsha", "al quoz", "marina",
)

# The "Dubai Creek" cutoff line, as two points (lat, lon)→(lat, lon). It follows the Creek
# down from the Deira/Sharjah side to Ras Al Khor and on inland — the line where Dubai meets
# Sharjah with the big waterway through the city. Listings on the NORTHEAST / EAST side of it
# (Deira, Al Garhoud, Al Nahda, Al Qusais, Al Muhaisnah toward Sharjah, plus the far-east
# inland: International City, Al Warqa'a, Al Warsan, Silicon Oasis, DLRC) are hidden; the
# coastal/central southwest side (Jumeirah, Satwa, Bur Dubai, Business Bay, Al Jaddaf …) and
# the western/southern areas are kept. See keep_sw_of_line in Criteria.
CREEK_LINE = (25.28, 55.315, 25.00, 55.42)

# Property Finder location ids per emirate (the `l=` search param; also path[0] of a
# listing's location path). Verified live Oct 2025. Lets the scan cover more than Dubai.
EMIRATE_IDS = {"dubai": 1, "sharjah": 4, "ajman": 5}

# "Central Dubai" polygon (lat, lon vertices). When drop_far_out is on, Dubai listings
# OUTSIDE this shape are dropped — the far-out areas: the Dubailand belt (DLRC, Liwan,
# Majan, City of Arabia, Town Square, Rukan, Damac Hills, Villanova), the far-east inland
# (Silicon Oasis, International City, Al Warqa, Nadd Al Hammar), the far-south (Dubai South,
# Expo) and the far-west strip toward Palm Jebel Ali (Al Furjan, Discovery Gardens, The
# Gardens, Wasl Gate, Jebel Ali). It keeps the coast, the central city, and the whole JVC
# cluster (JVC/JVT, Sports City, Arjan, Motor City, Studio City, Production City). Only
# applies to Dubai listings (emirate_id 1). Calibrated from real listing coordinates.
CENTRAL_DUBAI = (
    (25.30, 55.255), (25.30, 55.385), (25.20, 55.385), (25.16, 55.315), (25.095, 55.295),
    (25.055, 55.265), (25.02, 55.232), (25.00, 55.205), (25.02, 55.183), (25.05, 55.168),
    (25.075, 55.150), (25.065, 55.125), (25.10, 55.120), (25.16, 55.185), (25.21, 55.235),
    (25.27, 55.260),
)


# Area quality tiers. The point is NOT how far out an area is (a newer far community like
# JVC, Sports City, Town Square or Dubai South is perfectly fine) — it's how the place
# FEELS: genuinely nice/upscale vs. run-down, old and dense. Only two things get flagged;
# everything else is neutral (no colour):
#   "nice"    — genuinely upscale / coastal / well-kept, highly rated by residents.
#   "caution" — run-down, old and dense "old-Dubai" stretches (the user's examples:
#               International City and the old-town Deira/Bur Dubai area). Distance alone
#               never puts an area here.
# Sources: Khaleej Times resident survey + Bayut / Property Finder community guides (Oct
# 2025). Matched as a substring against the area string, MOST SPECIFIC FIRST (first match
# wins). Anything not listed defaults to the neutral middle. (substr, tier, one-line reason).
AREA_TIERS = (
    # Listed before the bare "jumeirah"/"downtown" entries so they don't match those.
    ("jumeirah village triangle", "mid", ""),
    ("jumeirah village circle", "mid", ""),
    ("jumeirah garden city", "caution", "Old, dense Satwa-side redevelopment"),
    ("al satwa", "caution", "Old, cheap, very dense and run-down central district"),
    ("al badaa", "mid", ""),
    ("downtown jebel ali", "mid", ""),   # far, but not run-down — stays neutral
    # Genuinely nice / upscale / well-kept.
    ("palm jumeirah", "nice", "Prime beachfront community"),
    ("umm suqeim", "nice", "Established coastal Jumeirah, beaches & villas"),
    ("madinat jumeirah", "nice", "Prime coastal resort district"),
    ("al sufouh", "nice", "Coastal, between Jumeirah and the Marina"),
    ("al wasl", "nice", "Smart central coastal strip by the canal"),
    ("city walk", "nice", "Upscale, walkable, modern central district"),
    ("bluewaters", "nice", "Premium waterfront island"),
    ("jumeirah", "nice", "Coastal Jumeirah — top-rated by residents"),
    ("dubai hills", "nice", "Green, clean, upscale family community"),
    ("mohammed bin rashid", "nice", "Upscale master-planned district (MBR City)"),
    ("district one", "nice", "Upscale MBR City lagoon community"),
    ("meydan", "nice", "Upscale, newer, near Downtown"),
    ("downtown dubai", "nice", "Prime central district — top infrastructure"),
    ("business bay", "nice", "Modern, well-kept central hub"),
    ("motor city", "nice", "Voted #1 by residents — clean, well-laid-out"),
    ("the greens", "nice", "Resident favourite — safe, green, walkable"),
    ("the views", "nice", "Established, green, well-kept"),
    ("emirates living", "nice", "Established, well-kept villa community"),
    ("dubai hills estate", "nice", "Green, clean, upscale family community"),
    # Run-down / old / dense — "I don't want to live there" (not about distance).
    ("bur dubai", "caution", "Old-town Dubai — crowded, old and run-down in parts"),
    ("deira", "caution", "Old Dubai — crowded, old and run-down"),
    ("international city", "caution", "Dense, cheap, poorly-kept blocks"),
    ("al nahda", "caution", "Old, dense, Sharjah-border area"),
    ("al qusais", "caution", "Old, dense, Sharjah-border area"),
    ("al muhaisnah", "caution", "Old, dense, industrial-adjacent"),
    ("al quoz", "caution", "Industrial, dusty, not really residential"),
    ("al warqa", "caution", "Older, plain, far-east residential"),
    ("al karama", "caution", "Old-town Dubai — crowded and dense"),
    ("karama", "caution", "Old-town Dubai — crowded and dense"),
)


def area_tier(area: str) -> tuple[str, str]:
    """Return (tier, reason) for an area string. Defaults to a neutral 'mid' when unknown."""
    a = (area or "").lower()
    for substr, tier, reason in AREA_TIERS:
        if substr in a:
            return tier, reason
    return "mid", ""


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
    # Use Property Finder's MONTHLY price-range search route (/en/search?c=2&rp=m&pt=<max>&
    # bdr[]=<n>) instead of the per-bedroom slug. The slug URL ignores price params and only
    # sorts, so raising the budget did nothing — the cheapest 16 pages still topped out at
    # ~6k. This route filters by monthly price server-side, so `max_price_monthly_aed` is a
    # real ceiling and the whole 0→budget range is reachable (fetched from both ends via
    # pa+pd so coverage is complete). This is how the main tab honours its budget.
    pf_monthly_price_search: bool = False
    # Float real coastal-Jumeirah listings (COASTAL_JUMEIRAH_IDS) to the top of the ranked
    # results, before everything else, still cheapest-first within each group.
    jumeirah_first: bool = False
    # Also query the coastal-Jumeirah communities directly and merge them in, so the handful
    # of in-budget Jumeirah flats aren't missed by the all-Dubai price-band sampling. Kept
    # separate from jumeirah_first so they can be included without being floated to the top.
    pf_include_jumeirah: bool = False
    # Geographic cutoff: (lat1, lon1, lat2, lon2). When set, a listing WITH coordinates is
    # dropped if it falls on the northeast/east side of this line (see CREEK_LINE). Listings
    # without coordinates are kept (can't place them).
    keep_sw_of_line: tuple[float, float, float, float] | None = None
    # Drop Dubai listings that fall outside the CENTRAL_DUBAI polygon (far-out areas:
    # Dubailand, far-east inland, far-south, and the far-west toward Palm Jebel Ali).
    drop_far_out: bool = False
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

    # Which emirates to actually search, by name (keys of EMIRATE_IDS: dubai/sharjah/ajman).
    # The price-band search queries each one's Property Finder location, and any emirate
    # listed here is NOT dropped by excluded_emirates above. Default: Dubai only.
    emirates: tuple[str, ...] = ("dubai",)

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


# Main Flatshare tab: Dubai 2-bed, cheapest-first. Budget capped at 6.5k and far-out areas
# (Dubailand / far suburbs / Palm-Jebel-Ali side) dropped — see CENTRAL_DUBAI. These are
# also exposed in the ⚙ Setup wizard so each user can change them without code.
CRITERIA = Criteria(
    max_price_monthly_aed=6500,
    # Don't require an exact bathroom count. Most Dubai 2-beds are quoted with 3 bathrooms,
    # so demanding exactly 2 dropped more than half of them (incl. real 2-beds in Jumeirah)
    # — which then only showed on the Jumeirah tab. The flat count is what matters here, not
    # the bathrooms, so accept any bathroom count.
    bathrooms=None,
    pf_monthly_price_search=True,
    # Pure cheapest-first: all the sub-6k flats lead the list. (No preferred-area tier — an
    # empty preferred_areas means the sort key is price alone.)
    preferred_areas=(),
    jumeirah_first=False,
    pf_include_jumeirah=True,   # still pull the in-budget Jumeirah flats; they sort by price
    drop_far_out=True,          # drop Dubailand / far suburbs / Palm-Jebel-Ali side
    # Hide everything on the Sharjah/Deira side of the Dubai Creek (see CREEK_LINE).
    keep_sw_of_line=CREEK_LINE,
    # Each price band is fetched from BOTH ends (pa cheapest + pd dearest) so the band's
    # full width is covered despite PF's ~50-page cap. 5 bands (≤6k + 500/mo steps) × 2
    # orderings × 10 pages ≈ 100 requests, ~14s on Vercel — full 4.3k→8k spread.
    pf_orderings=("pa", "pd"),
    pf_max_pages=10,
)


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
    pf_location_ids=COASTAL_JUMEIRAH_IDS,
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
