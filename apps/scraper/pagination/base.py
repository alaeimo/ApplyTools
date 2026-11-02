"""Pagination strategy Protocol. Each strategy is a pure sync function —
trivially unit-testable without any HTTP or DB."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..domain.models import FetchResult, SiteConfig


@runtime_checkable
class PaginationStrategy(Protocol):
    def next_url(
        self,
        current_url: str,
        current_page: int,
        last_result: Optional[FetchResult],
        config: SiteConfig,
    ) -> Optional[str]:
        """Return the next URL to fetch, or None if pagination is exhausted."""
        ...
