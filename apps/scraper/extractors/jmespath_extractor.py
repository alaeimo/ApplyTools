"""JMESPath extractor — declarative JSON extraction with native list support.

Replaces the original scraper's dot-notation get_nested_value() which broke on
arrays and required 4+ per-site config fields.
"""
from __future__ import annotations

import logging
from typing import Optional

import jmespath

from ..domain.models import FetchResult, PositionExtracted, SiteConfig
from ..parsers.text import html_to_text
from ..parsers.url import absolute_url

log = logging.getLogger(__name__)

# Sensible JMESPath defaults — auto-detected for common API shapes.
_DEFAULT_URL_EXPR = jmespath.compile("url")
_DEFAULT_TITLE_EXPR = jmespath.compile("title || name")
_DEFAULT_COMPANY_EXPR = jmespath.compile(
    "company.name || company || organization.name || employer || hiringOrganization.name"
)
_DEFAULT_DESC_EXPR = jmespath.compile("description || content || body || summary")


class JmespathExtractor:
    """Extract positions from JSON APIs using JMESPath expressions."""

    name = "jmespath"

    async def extract_listing(
        self, result: FetchResult, config: SiteConfig
    ) -> list[PositionExtracted]:
        if not result.is_json or not config.api_results_jmespath:
            return []

        try:
            data = result.json()
        except Exception as e:
            log.warning("Invalid JSON on %s: %s", result.url, e)
            return []

        try:
            items_expr = jmespath.compile(config.api_results_jmespath)
        except jmespath.exceptions.ParseError as e:
            log.error("Invalid JMESPath %r: %s", config.api_results_jmespath, e)
            return []

        items = items_expr.search(data) or []
        if not isinstance(items, list):
            items = [items]

        base = str(config.detail_api_endpoint or config.base_url)
        # Ensure base ends with '/' so urljoin appends rather than replaces
        if not base.endswith("/"):
            base += "/"
        out: list[PositionExtracted] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url_value = _DEFAULT_URL_EXPR.search(item)
            if not url_value:
                continue
            full_url = absolute_url(base, str(url_value))
            title = _DEFAULT_TITLE_EXPR.search(item) or "Unknown Title"
            company = _DEFAULT_COMPANY_EXPR.search(item) or ""
            desc = _DEFAULT_DESC_EXPR.search(item) or ""
            out.append(PositionExtracted(
                url=full_url,
                title=str(title),
                company=str(company),
                cleaned_text=html_to_text(str(desc)),
                raw_data=item,
                extractor_used=self.name,
                confidence=0.9,
            ))
        return out

    async def extract_detail(
        self, result: FetchResult, config: SiteConfig
    ) -> Optional[PositionExtracted]:
        if not result.is_json or not config.detail_jmespath:
            return None
        try:
            data = result.json()
        except Exception:
            return None
        try:
            expr = jmespath.compile(config.detail_jmespath)
        except jmespath.exceptions.ParseError:
            return None
        detail = expr.search(data)
        if detail is None:
            return None
        if isinstance(detail, dict):
            text = html_to_text(str(detail.get("description") or detail))
            raw = detail
        elif isinstance(detail, str):
            text = html_to_text(detail)
            raw = {"value": detail}
        else:
            text = str(detail)
            raw = {"value": detail}
        return PositionExtracted(
            url=result.url,
            title="",
            company="",
            cleaned_text=text,
            raw_data=raw,
            extractor_used=self.name,
            confidence=0.85,
        )
