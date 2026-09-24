"""Approximate coordinates for Dubai communities, keyed by area-name substring.

Some sources (Dubizzle via Apify, most Facebook posts) give an area name but no
lat/lon, so their listings can't be placed on the map. This maps an area string to the
community's approximate centre so those listings still get a pin (flagged approximate).
Coordinates are rough community centroids — good enough to see roughly where a listing
is, not exact. Matching prefers the LONGEST key found in the string, so
"Jumeirah Village Circle" wins over the generic "jumeirah".
"""
from __future__ import annotations

# area substring (lower-case) -> (lat, lon)
DUBAI_AREAS: dict[str, tuple[float, float]] = {
    # Coastal / Jumeirah strip
    "jumeirah 1": (25.213, 55.255),
    "jumeirah 2": (25.196, 55.238),
    "jumeirah 3": (25.175, 55.225),
    "port de la mer": (25.244, 55.267),
    "pearl jumeirah": (25.235, 55.263),
    "la mer": (25.226, 55.258),
    "city walk": (25.205, 55.263),
    "al wasl": (25.198, 55.253),
    "madinat jumeirah": (25.133, 55.183),
    "umm suqeim": (25.145, 55.195),
    "al sufouh": (25.108, 55.176),
    "palm jumeirah": (25.116, 55.138),
    "bluewaters": (25.079, 55.122),
    "jumeirah beach residence": (25.078, 55.134),
    "jbr": (25.078, 55.134),
    "dubai marina": (25.080, 55.141),
    "marina": (25.080, 55.141),
    "emaar beachfront": (25.093, 55.144),
    "dubai harbour": (25.093, 55.148),
    "jumeirah": (25.200, 55.245),  # generic fallback for coastal Jumeirah
    # Inland "Jumeirah *" look-alikes
    "jumeirah village circle": (25.058, 55.209),
    "jumeirah village triangle": (25.052, 55.192),
    "jvc": (25.058, 55.209),
    "jvt": (25.052, 55.192),
    "jumeirah lake towers": (25.069, 55.144),
    "jlt": (25.069, 55.144),
    "jumeirah islands": (25.062, 55.155),
    "jumeirah park": (25.048, 55.160),
    "jumeirah golf estates": (25.030, 55.198),
    # Central Dubai
    "business bay": (25.187, 55.263),
    "downtown": (25.197, 55.274),
    "difc": (25.212, 55.281),
    "zabeel": (25.220, 55.290),
    "al satwa": (25.221, 55.273),
    "jumeirah garden city": (25.225, 55.278),
    "al jaddaf": (25.223, 55.330),
    "meydan": (25.160, 55.300),
    "nad al sheba": (25.160, 55.330),
    "al barsha": (25.112, 55.196),
    "barsha heights": (25.098, 55.178),
    "tecom": (25.098, 55.178),
    "dubai hills": (25.100, 55.240),
    "the greens": (25.098, 55.171),
    "the views": (25.095, 55.165),
    "media city": (25.095, 55.158),
    "internet city": (25.093, 55.163),
    "al furjan": (25.026, 55.145),
    "discovery gardens": (25.043, 55.147),
    "the gardens": (25.043, 55.147),
    "motor city": (25.045, 55.238),
    "sports city": (25.037, 55.222),
    "arjan": (25.055, 55.240),
    "dubailand": (25.050, 55.250),
    "silicon oasis": (25.121, 55.378),
    "international city": (25.163, 55.408),
    "warsan": (25.155, 55.415),
    "dubai festival city": (25.222, 55.353),
    "creek harbour": (25.200, 55.345),
    "ras al khor": (25.180, 55.350),
    # Older / northern Dubai
    "deira": (25.271, 55.316),
    "bur dubai": (25.258, 55.297),
    "al rigga": (25.267, 55.320),
    "al nahda": (25.294, 55.372),
    "al qusais": (25.283, 55.393),
    "al warqa": (25.180, 55.400),
    "mirdif": (25.216, 55.418),
    "muhaisnah": (25.278, 55.410),
    "dubai islands": (25.290, 55.315),
    "mina rashid": (25.245, 55.290),
}

# Longest keys first so the most specific area wins the match.
_KEYS_BY_LEN = sorted(DUBAI_AREAS, key=len, reverse=True)


def approx_coords(area: str | None) -> tuple[float | None, float | None]:
    """Best-effort (lat, lon) for an area string, or (None, None) if unknown."""
    if not area:
        return (None, None)
    a = area.lower()
    for key in _KEYS_BY_LEN:
        if key in a:
            return DUBAI_AREAS[key]
    return (None, None)
