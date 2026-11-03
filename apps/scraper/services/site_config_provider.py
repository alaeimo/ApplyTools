"""Service layer — bridges Django Website model → declarative SiteConfig.

Updated: handles max_pages=0 as "unlimited" (capped at 1000) instead of
converting it to the default 10.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..domain.models import PaginationConfig, SiteConfig
from ..domain.enums import ScrapingMethod

log = logging.getLogger(__name__)

# When max_pages=0 (unlimited), use this cap to avoid infinite loops
MAX_PAGES_UNLIMITED_CAP = 1000

def _or_none(value):
    """Convert empty strings to None (for Pydantic Optional[HttpUrl] fields)."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value

def website_to_config(website) -> SiteConfig:
    """Map Django Website model → Pydantic SiteConfig (declarative)."""
    method_str = getattr(website, "scraping_method", "html") or "html"
    try:
        method = ScrapingMethod(method_str)
    except ValueError:
        method = ScrapingMethod.HTML

    # ─── Pagination config ────────────────────────────────────
    pagination: Optional[PaginationConfig] = None
    pagination_param = getattr(website, "api_pagination_param", None)
    if pagination_param:
        is_offset = pagination_param.lower() in ("offset", "start", "skip", "from")
        pagination = PaginationConfig(
            type="offset" if is_offset else "page",
            param=pagination_param,
            limit_param=getattr(website, "api_limit_param", None) or "limit",
            limit_value=10,
        )

    # ─── Convert dot-notation to JMESPath ─────────────────────
    api_results_jmespath: Optional[str] = None
    if getattr(website, "api_results_key", None):
        api_results_jmespath = _dot_to_jmespath(website.api_results_key)

    detail_jmespath: Optional[str] = None
    if getattr(website, "api_detail_key", None):
        detail_jmespath = _dot_to_jmespath(website.api_detail_key)

    # ─── Extraction priority based on method ─────────────────
    if method == ScrapingMethod.API:
        priority = ["jmespath", "jsonld", "css"]
    elif method == ScrapingMethod.JSONLD:
        priority = ["jsonld", "css", "jmespath"]
    elif method == ScrapingMethod.BROWSER:
        priority = ["jsonld", "css", "jmespath"]
    else:  # HTML
        priority = ["jsonld", "css", "jmespath"]

    # ─── Randomized politeness delay ───────────────────────────
    delay = getattr(website, "request_delay", None) or 0
    request_delay = (max(0.1, delay * 0.5), delay * 2.0) if delay else (1.5, 6.0)

    # ─── max_pages: 0 means unlimited ─────────────────────────
    website_max_pages = getattr(website, "max_pages", None)
    if website_max_pages and website_max_pages > 0:
        max_pages = website_max_pages
    else:
        max_pages = MAX_PAGES_UNLIMITED_CAP

    # ─── Determine if site needs JS ───────────────────────────
    needs_js = (method == ScrapingMethod.BROWSER) or getattr(website, "needs_js", False)

    return SiteConfig(
        name=website.name,
        base_url=_or_none(website.base_url),
        list_url=getattr(website, "list_url", None),
        api_endpoint=_or_none(website.api_endpoint) if method == ScrapingMethod.API else None,
        api_results_jmespath=api_results_jmespath,
        api_pagination=pagination,
        api_auth_token=getattr(website, "api_auth_token", None),
        api_headers={}, 
        api_extra_params=dict(getattr(website, "api_extra_params", None) or {}),
        needs_js=needs_js,
        listing_css=getattr(website, "listing_item_selector", None),
        link_css=getattr(website, "position_link_selector", None),
        title_css=getattr(website, "position_title_selector", None),
        company_css=getattr(website, "position_company_selector", None),
        detail_api_endpoint=_or_none(getattr(website, "detail_api_endpoint", None)),
        detail_jmespath=detail_jmespath,
        detail_container_css=getattr(website, "detail_container_selector", None),
        max_pages=max_pages,
        request_timeout=getattr(website, "request_timeout", None) or 30.0,
        request_delay=request_delay,
        max_concurrency=getattr(website, "max_concurrency", 5),
        use_browser_fallback=getattr(website, "use_browser_fallback", True),
        extractor_priority=priority,
    )


def _dot_to_jmespath(dot_key: str) -> str:
    """Convert 'data.items' dot notation to JMESPath-compatible expression.

    JMESPath uses the same dot syntax for nested objects, but supports richer
    queries (e.g. 'jobs[*]', 'results[?status==`open`]'). If the old key looks
    like it should produce a list, append '[*]' automatically.
    """
    if not dot_key:
        return ""
    last_segment = dot_key.split(".")[-1].lower()
    if last_segment in {"items", "results", "jobs", "list", "positions", "data"}:
        return f"{dot_key}[*]"
    return dot_key
