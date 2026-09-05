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
