from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Criteria
from ..models import Listing


class Source(ABC):
    """Common interface every listing source implements."""

    name: str

    @abstractmethod
    def fetch(self, criteria: Criteria) -> list[Listing]:
        """Return raw listings for the given criteria (source-side filtering is a
        best-effort optimization; final filtering always happens in scanner.filters)."""
        raise NotImplementedError


def page_diagnostic(page, cards_found: int, challenge_markers: tuple[str, ...]) -> dict:
    """Snapshot why a browser-scraped page yielded what it did.

    Distinguishes the two silent-zero cases for a bot-protected portal: the page was a
    challenge/empty shell (looks_blocked, tiny html, no __NEXT_DATA__) vs. the real page
    loaded but our selectors matched nothing (has_next_data True, cards_found 0). Written
    into browser_sources.json so a 0-result run explains itself instead of being a mystery.
    """
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    try:
        html = page.content() or ""
    except Exception:
        html = ""
    head = html[:6000].lower()
    return {
        "title": title[:200],
        "html_len": len(html),
        "cards_found": cards_found,
        "has_next_data": "__next_data__" in head,
        "looks_blocked": any(m in head for m in challenge_markers),
    }
