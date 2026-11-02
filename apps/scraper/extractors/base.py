"""Extractor Protocol — pure async functions that turn a FetchResult into
PositionExtracted items. No I/O inside."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import FetchResult, PositionExtracted, SiteConfig


@runtime_checkable
class Extractor(Protocol):
    name: str

    async def extract_listing(
        self, result: FetchResult, config: SiteConfig
    ) -> list[PositionExtracted]:
        ...

    async def extract_detail(
        self, result: FetchResult, config: SiteConfig
    ) -> PositionExtracted | None:
        ...
