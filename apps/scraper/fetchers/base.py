"""Fetcher Protocol — the only contract the rest of the system depends on.
Concrete implementations live in http_fetcher.py and browser_fetcher.py."""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from ..domain.models import FetchResult, SiteConfig


@runtime_checkable
class Fetcher(Protocol):
    """Async fetcher contract. Implementations MUST be safe to call concurrently."""

    async def fetch(
        self,
        url: str,
        config: SiteConfig,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[dict[str, Any]] = None,
        use_browser: bool = False,
    ) -> Optional[FetchResult]:
        """Fetch a URL and return a FetchResult, or None on permanent failure."""
        ...

    async def close(self) -> None:
        """Release resources (HTTP session, browser process)."""
        ...
