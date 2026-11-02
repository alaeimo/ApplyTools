"""Pipeline Protocol — what to do with each scraped PositionExtracted."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import PositionExtracted


@runtime_checkable
class Pipeline(Protocol):
    async def process(self, item: PositionExtracted) -> bool:
        """Return True if item was processed (saved), False if skipped (dup)."""
        ...

    async def close(self) -> None: ...
