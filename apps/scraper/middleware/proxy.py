"""Round-robin proxy pool. Pass entries like 'http://user:pass@host:port'."""
from __future__ import annotations

import itertools
from typing import Iterable, Optional


class ProxyPool:
    """Cycle proxies in round-robin order. Empty pool means 'no proxy'."""

    def __init__(self, proxies: Iterable[str] | None = None):
        self._proxies = list(proxies or [])
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    def next(self) -> Optional[str]:
        if not self._cycle:
            return None
        return next(self._cycle)

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def __len__(self) -> int:
        return len(self._proxies)
