"""CSS extractor using selectolax (5-10x faster than BeautifulSoup + html.parser).
Self-healing fallbacks: tries multiple selectors before giving up."""
from __future__ import annotations

import logging
from typing import Optional

try:
    # selectolax >= 1.0 — lexbor backend (actively maintained)
    from selectolax.lexbor import LexborHTMLParser as HTMLParser
except ImportError:  # pragma: no cover — fallback for older versions
    from selectolax.parser import HTMLParser

from ..domain.models import FetchResult, PositionExtracted, SiteConfig
from ..parsers.url import absolute_url

log = logging.getLogger(__name__)

# Fallback title selectors tried when the configured one fails
_TITLE_FALLBACKS = ["h1", "h2", "h3", ".title", ".job-title", "[data-title]"]
_COMPANY_FALLBACKS = [".company", ".employer", ".organization", "[data-company]"]


class CssExtractor:
    """Extract positions from HTML using CSS selectors + selectolax."""

    name = "css"

    async def extract_listing(
        self, result: FetchResult, config: SiteConfig
    ) -> list[PositionExtracted]:
        if not result.is_html or not (config.listing_css and config.link_css):
            return []

        tree = HTMLParser(result.text)
        out: list[PositionExtracted] = []
        for node in tree.css(config.listing_css):
            link = node.css_first(config.link_css)
            if not link:
                continue
            href = link.attributes.get("href")
            if not href:
                continue
            url = absolute_url(result.url, href.strip())
            title = _extract_text(node, config.title_css) or _extract_text(link, None)
            if not title:
                title = _try_fallbacks(node, _TITLE_FALLBACKS)
            company = _extract_text(node, config.company_css)
            if not company:
                company = _try_fallbacks(node, _COMPANY_FALLBACKS)
            out.append(PositionExtracted(
                url=url,
                title=title or "Unknown Title",
                company=company,
                extractor_used=self.name,
                confidence=0.7,
            ))
        return out

    async def extract_detail(
        self, result: FetchResult, config: SiteConfig
    ) -> Optional[PositionExtracted]:
        if not result.is_html or not config.detail_container_css:
            return None
        tree = HTMLParser(result.text)
        node = tree.css_first(config.detail_container_css)
        if not node:
            return None
        # Strip script/style before extracting text
        for tag in node.css("script, style, noscript"):
            tag.decompose()
        text = node.text(separator="\n", strip=True)
        return PositionExtracted(
            url=result.url,
            title="",
            company="",
            cleaned_text=text,
            extractor_used=self.name,
            confidence=0.8,
        )


def _extract_text(node, selector: Optional[str]) -> str:
    if not selector:
        return ""
    sub = node.css_first(selector)
    return sub.text(strip=True) if sub else ""


def _try_fallbacks(node, selectors: list[str]) -> str:
    for sel in selectors:
        text = _extract_text(node, sel)
        if text:
            return text
    return ""
