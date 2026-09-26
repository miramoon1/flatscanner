from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    source: str  # "bayut" | "dubizzle" | "propertyfinder" | "facebook"
    source_id: str  # id/slug as given by the source, unique within that source
    title: str
    url: str
    price_monthly_aed: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    area: str  # e.g. "Jumeirah 1, Jumeirah, Dubai"
    image_url: Optional[str] = None
    listed_at: Optional[str] = None  # ISO 8601 date the listing was posted, when the source exposes it
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Property Finder community id (path[1] of the location path, e.g. 66 = Jumeirah).
    # Used to identify the real coastal-Jumeirah communities precisely, since the area
    # NAME is often just "Jumeirah" and can't be told apart from Jumeirah Village etc.
    community_id: Optional[int] = None
    scraped_at: str = ""

    def __post_init__(self) -> None:
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

    @property
    def id(self) -> str:
        raw = f"{self.source}:{self.source_id}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d
