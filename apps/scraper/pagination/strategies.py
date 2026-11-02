"""Pagination strategies: page-based, offset-based, cursor-based, link-based.
Each is pure sync — easy to unit test with no HTTP."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urljoin

import jmespath
try:
    from selectolax.lexbor import LexborHTMLParser as HTMLParser
except ImportError:  # pragma: no cover
    from selectolax.parser import HTMLParser

from ..domain.models import FetchResult, PaginationConfig, SiteConfig


class PageStrategy:
    """?page=N&limit=M — most common pattern."""

    def __init__(self, cfg: PaginationConfig):
        self.cfg = cfg

    def next_url(
        self,
        current_url: str,
        current_page: int,
        last_result: Optional[FetchResult],
        config: SiteConfig,
    ) -> Optional[str]:
        next_page = current_page + 1
        if next_page > config.max_pages:
            return None
        return _set_query(current_url, {
            self.cfg.param: next_page,
            **({self.cfg.limit_param: self.cfg.limit_value} if self.cfg.limit_param else {}),
        })


class OffsetStrategy:
    """?offset=N&limit=M."""

    def __init__(self, cfg: PaginationConfig):
        self.cfg = cfg

    def next_url(
        self,
        current_url: str,
        current_page: int,
        last_result: Optional[FetchResult],
        config: SiteConfig,
    ) -> Optional[str]:
        next_offset = current_page * self.cfg.limit_value
        if current_page >= config.max_pages:
            return None
        return _set_query(current_url, {
            self.cfg.param: next_offset,
            **({self.cfg.limit_param: self.cfg.limit_value} if self.cfg.limit_param else {}),
        })


class CursorStrategy:
    """Cursor-based pagination — extract cursor from last response via JMESPath.
    Typical for GraphQL APIs (Relay connection pattern)."""

    def __init__(self, cfg: PaginationConfig):
        self.cfg = cfg

    def next_url(
        self,
        current_url: str,
        current_page: int,
        last_result: Optional[FetchResult],
        config: SiteConfig,
    ) -> Optional[str]:
        if not last_result or not self.cfg.cursor_path:
            return None
        if current_page >= config.max_pages:
            return None
        try:
            data = last_result.json()
        except Exception:
            return None
        cursor = jmespath.search(self.cfg.cursor_path, data)
        if not cursor or cursor == "null":
            return None
        return _set_query(current_url, {self.cfg.param: cursor})


class LinkStrategy:
    """HTML <a rel="next"> link — for sites that paginate via links."""

    def __init__(self, cfg: PaginationConfig):
        self.cfg = cfg

    def next_url(
        self,
        current_url: str,
        current_page: int,
        last_result: Optional[FetchResult],
        config: SiteConfig,
    ) -> Optional[str]:
        if not last_result or not last_result.is_html:
            return None
        if current_page >= config.max_pages:
            return None
        tree = HTMLParser(last_result.text)
        selector = self.cfg.next_link_selector or 'a[rel="next"], a.next, a[class*="next"]'
        node = tree.css_first(selector)
        if not node:
            return None
        href = node.attributes.get("href")
        return urljoin(current_url, href) if href else None


def make_strategy(cfg: Optional[PaginationConfig]) -> Optional[object]:
    """Factory that maps a PaginationConfig to a strategy instance."""
    if not cfg:
        return None
    mapping = {
        "page": PageStrategy,
        "offset": OffsetStrategy,
        "cursor": CursorStrategy,
        "link": LinkStrategy,
    }
    cls = mapping.get(cfg.type)
    return cls(cfg) if cls else None


def _set_query(url: str, updates: dict) -> str:
    """Set/update query params on a URL, preserving everything else."""
    p = urlparse(url)
    qs = dict(parse_qsl(p.query, keep_blank_values=True))
    qs.update({k: str(v) for k, v in updates.items()})
    return p._replace(query=urlencode(qs)).geturl()
