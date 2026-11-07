"""Website auto-analyzer service.

Fetches the listing + detail HTML via the existing AutoFetcher, cleans the HTML
(removes scripts/styles/SVGs/comments/inline-styles to fit DeepSeek's context
window), then asks DeepSeek to return the exact Website model fields needed to
scrape that site.

Used by apps.websites.views.analyze_website (POST /api/v1/websites/analyze/).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse, urljoin

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ─── Public exception types ─────────────────────────────────

class AnalyzeError(Exception):
    """Base class — message is safe to show to the user."""

    def __init__(self, message: str, reason: str = "error"):
        super().__init__(message)
        self.reason = reason
        self.message = message


class BlockedError(AnalyzeError):
    """Site blocked the scraper (Cloudflare, login wall, etc.)."""

    def __init__(self, message: str = "Website blocked the scraper."):
        super().__init__(message, reason="blocked")


class InvalidURLError(AnalyzeError):
    def __init__(self, message: str = "Invalid URL"):
        super().__init__(message, reason="invalid_url")


# ─── HTML cleaning ──────────────────────────────────────────

_DROP_TAGS = {"script", "style", "svg", "noscript", "iframe", "link", "meta"}
_STYLE_ATTR_RE = re.compile(r'\s+style="[^"]*"')


def _clean_html(html: str, *, max_chars: int = 30000) -> str:
    if not html:
        return ""
    soup = _make_soup(html)
    for tag_name in _DROP_TAGS:
        for tag in soup.css(tag_name):
            tag.decompose()
    text = soup.html or soup
    html_str = str(text)
    html_str = re.sub(r"<!--.*?-->", "", html_str, flags=re.DOTALL)
    html_str = _STYLE_ATTR_RE.sub("", html_str)
    html_str = re.sub(r"\s+", " ", html_str).strip()
    if len(html_str) > max_chars:
        head = html_str[: max_chars // 2]
        tail = html_str[-(max_chars // 4):]
        html_str = head + "\n<!-- truncated -->\n" + tail
    return html_str


def _make_soup(html: str):
    try:
        from selectolax.lexbor import LexborHTMLParser
        return LexborHTMLParser(html)
    except Exception:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser")


# ─── DeepSeek integration ──────────────────────────────────

def _ask_deepseek(prompt: str) -> dict:
    from apps.ai.deepseek import DeepSeekClient
    client = DeepSeekClient()
    try:
        reply = client.chat(prompt)
    finally:
        try:
            client.close()
        except Exception:
            pass
    return _parse_json_reply(reply.text)


def _parse_json_reply(text: str) -> dict:
    if not text:
        raise AnalyzeError("DeepSeek returned an empty response.")
    cleaned = text.strip()
    if cleaned.startswith("\ufeff"):
        cleaned = cleaned.lstrip("\ufeff").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as e:
            for shrink_end in range(end, start, -1):
                if cleaned[shrink_end] != "}":
                    continue
                sub = cleaned[start:shrink_end + 1]
                try:
                    data = json.loads(sub)
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    continue
            raise AnalyzeError(f"DeepSeek returned malformed JSON: {e}") from None
    raise AnalyzeError("DeepSeek returned no parseable JSON object.")


# ─── Prompt templates ──────────────────────────────────────

_LISTING_PROMPT = """You are an expert web-scraping engineer who specializes in academic position websites (PhD, postdoc, faculty job boards).

I will give you (1) the cleaned HTML of a LISTING PAGE, and (2) optionally a list of XHR/JSON API responses captured while the page loaded. Your job: identify the CSS selectors OR the API configuration your scraper should use.

Return ONLY a single valid JSON object — no markdown, no explanation, no thinking prose. The JSON must have EXACTLY this shape:

{{
  "scraping_method": "html" | "api",
  "needs_js": true | false,
  "use_browser_fallback": true | false,
  "listing_item_selector": "<CSS selector for the OUTER container of each position card; empty if scraping_method is api>",
  "position_link_selector":  "<CSS selector for the <a> element inside the card; empty if api>",
  "position_title_selector": "<CSS selector for the title element; empty if api>",
  "position_company_selector": "<CSS selector for the institution name; empty if api or none>",
  "pagination_url_pattern": "<URL pattern with {{page}} placeholder; empty if pagination is via 'Next' link or API>",
  "api_endpoint": "<full API URL, only if scraping_method is api; empty otherwise>",
  "api_results_key": "<dot-notation path to the items array, e.g. 'data.jobs' or 'results'; empty if html>",
  "api_pagination_param": "<query param name for page number, e.g. 'page'; empty if html>",
  "api_limit_param": "<query param name for items per page, e.g. 'per_page'; empty if html>",
  "detected_detail_urls": ["<absolute URL of a sample detail page>"],
  "notes": "<short note about anything unusual>"
}}

DECISION RULES:
1. If the HTML contains position cards with class names like .job-card, .job-list-item, article.result — set scraping_method to "html" and fill the CSS selectors.
2. If the HTML is empty (e.g. <div id="root"></div>) BUT I gave you XHR responses — set scraping_method to "api", fill api_endpoint (use the XHR URL that returned the jobs list), api_results_key (the JSON path to the items array), and api_pagination_param.
3. If you see <script type="application/ld+json"> with schema.org JobPosting — set scraping_method to "html", leave all selectors empty, and mention JSON-LD in notes.
4. detected_detail_urls should contain 1-3 absolute URLs found in the listing.
5. NEVER invent selectors or API endpoints that don't appear in the data I gave you.

Here is the listing page URL for reference:
{url}

Here is the cleaned HTML:
---
{html}
---

Here are the captured XHR/JSON API responses (may be empty):
{xhrs}
---

Return the JSON object now."""


_DETAIL_PROMPT = """You are an expert web-scraping engineer who specializes in academic position websites.

I will give you the cleaned HTML of a DETAIL PAGE (a single position's full description). Your job: identify the CSS selector for the main content container that holds the full position description text.

Return ONLY a single valid JSON object — no markdown, no explanation, no code fences. The JSON must have EXACTLY this shape:

{{
  "detail_container_selector": "<CSS selector for the element that wraps the full position description>",
  "detail_source": "html",
  "notes": "<short note about anything unusual>"
}}

Rules you MUST follow:
1. Pick the selector that wraps the LARGEST meaningful chunk of position description text (the body content, not the header/footer/nav).
2. Prefer semantic class names ('.job-description', '.position-details') over utility classes ('.col-md-8').
3. If the page is empty (SPA), set "detail_container_selector": "" and explain in "notes".
4. NEVER invent a selector that doesn't exist in the HTML.

Here is the detail page URL for reference:
{url}

Here is the cleaned HTML:
---
{html}
---

Return the JSON object now."""


# ─── Fetching ──────────────────────────────────────────────

def _validate_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL is required.")
    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(url)
    except ValidationError as e:
        raise InvalidURLError(f"Invalid URL: {e}") from e
    return url.strip()


def _fetch_with_xhr(url: str) -> tuple[str, bool, Optional[str], list[dict]]:
    """Fetch a URL via BrowserFetcher with XHR capture + Cloudflare bypass.

    Returns (html, from_browser, error_msg, captured_xhrs).
    Each captured_xhr entry is {"url": "...", "json": {...}}.

    Uses BrowserFetcher.fetch() (which has stealth + Cloudflare waiting +
    content selector waiting). Falls back to AutoFetcher (nodriver) if
    Playwright fails.
    """
    import asyncio
    from apps.scraper.fetchers.browser_fetcher import BrowserFetcher
    from apps.scraper.domain.models import SiteConfig

    config = SiteConfig(
        name="analyzer",
        base_url=url,
        needs_js=True,
        use_browser_fallback=True,
        request_timeout=60.0,
        max_pages=1,
    )

    async def _do_fetch():
        fetcher = BrowserFetcher(headless=True, stealth=True)
        captured: list[dict] = []

        async def on_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if "json" not in ct.lower():
                    return
                if response.url == url:
                    return
                body = await response.text()
                try:
                    data = response.json()
                except Exception:
                    try:
                        data = json.loads(body)
                    except Exception:
                        return
                captured.append({
                    "url": response.url,
                    "status": response.status,
                    "json": data,
                })
            except Exception:
                pass

        try:
            result = await fetcher.fetch(url, config, on_response=on_response)
            if result is None:
                # Playwright failed entirely — fall back to AutoFetcher (nodriver)
                logger.info("BrowserFetcher returned None — falling back to AutoFetcher")
                html, from_browser, err = _fetch_html_sync(url)
                return html, from_browser, err, captured
            if result.status >= 400:
                return "", result.from_browser, f"http_{result.status}", captured
            # Check if we got a Cloudflare challenge page
            if "just a moment" in result.text.lower()[:2000]:
                logger.warning("Got Cloudflare challenge page — falling back to AutoFetcher")
                html, from_browser, err = _fetch_html_sync(url)
                if html and "just a moment" not in html.lower()[:2000]:
                    return html, from_browser, None, captured
                return "", from_browser, "blocked_challenge", captured
            return result.text, result.from_browser, None, captured
        except Exception as e:
            logger.warning("Browser fetch with XHR failed for %s: %s", url, e)
            # Last resort: try AutoFetcher (which has nodriver fallback)
            try:
                html, from_browser, err = _fetch_html_sync(url)
                if html:
                    return html, from_browser, err, captured
            except Exception:
                pass
            return "", False, f"exception:{type(e).__name__}", captured
        finally:
            try:
                await fetcher.close()
            except Exception:
                pass

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_do_fetch())
    finally:
        loop.close()


def _fetch_html_sync(url: str) -> tuple[str, bool, Optional[str]]:
    """Sync wrapper around _fetch_html for use inside async fallback."""
    # This is called from within an async context, so we can't use asyncio.run.
    # Instead, we directly call the AutoFetcher in a sub-loop.
    import asyncio
    from apps.scraper.fetchers.factory import AutoFetcher
    from apps.scraper.domain.models import SiteConfig

    config = SiteConfig(
        name="analyzer",
        base_url=url,
        needs_js=True,
        use_browser_fallback=True,
        request_timeout=60.0,
        max_pages=1,
    )

    async def _do():
        fetcher = AutoFetcher()
        try:
            result = await fetcher.fetch(url, config)
            if result is None:
                return "", False, "fetcher_returned_none"
            if result.status >= 400:
                return "", result.from_browser, f"http_{result.status}"
            return result.text, result.from_browser, None
        except Exception as e:
            return "", False, f"exception:{type(e).__name__}"
        finally:
            try:
                await fetcher.close()
            except Exception:
                pass

    # We're already in an event loop (called from _do_fetch), so use
    # asyncio.ensure_future to schedule and run to completion
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run in a nested loop to avoid "event loop is already running" error
    return asyncio.run(_do())


def _fetch_html(url: str) -> tuple[str, bool, Optional[str]]:
    """Fetch a URL with the AutoFetcher; return (html, from_browser, error_msg).

    AutoFetcher has the full fallback chain: HTTP (curl_cffi) → Playwright → nodriver.
    """
    import asyncio
    from apps.scraper.fetchers.factory import AutoFetcher
    from apps.scraper.domain.models import SiteConfig

    config = SiteConfig(
        name="analyzer",
        base_url=url,
        needs_js=True,
        use_browser_fallback=True,
        request_timeout=60.0,
        max_pages=1,
    )

    async def _do_fetch():
        fetcher = AutoFetcher()
        try:
            result = await fetcher.fetch(url, config)
            if result is None:
                return "", False, "fetcher_returned_none"
            if result.status >= 400:
                body_lower = result.text.lower()[:4000]
                if any(m in body_lower for m in ("cloudflare", "datadome", "akamai",
                                                 "just a moment", "checking your browser")):
                    return "", result.from_browser, "blocked_challenge"
                return "", result.from_browser, f"http_{result.status}"
            return result.text, result.from_browser, None
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", url, e)
            return "", False, f"exception:{type(e).__name__}"
        finally:
            try:
                await fetcher.close()
            except Exception:
                pass

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_do_fetch())
    finally:
        loop.close()


# ─── Public entry point ─────────────────────────────────────

def analyze_website(listing_url: str, detail_url: Optional[str] = None) -> dict:
    """Analyze a listing URL (and optionally a detail URL) and return suggested
    Website model fields + analysis metadata.
    """
    listing_url = _validate_url(listing_url)
    parsed = urlparse(listing_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    warnings: list[str] = []
    analysis: dict[str, Any] = {}

    # ─── Step 1: fetch listing page (with XHR capture) ───────
    listing_html, listing_from_browser, listing_err, captured_xhrs = _fetch_with_xhr(listing_url)

    if not listing_html and listing_err:
        raise AnalyzeError(
            f"Failed to fetch the listing page ({listing_err}). "
            "Try again, or add the website manually.",
            reason="fetch_failed",
        )

    cleaned_listing = _clean_html(listing_html)
    analysis["listing"] = {
        "html_size": len(listing_html),
        "cleaned_size": len(cleaned_listing),
        "used_browser": listing_from_browser,
        "xhr_count": len(captured_xhrs),
    }
    if listing_from_browser:
        warnings.append("Listing page required browser rendering (bot challenge or JS).")
    if captured_xhrs:
        warnings.append(f"Captured {len(captured_xhrs)} XHR/JSON responses — AI will analyze them for API endpoints.")

    # ─── Step 2: ask DeepSeek to analyze the listing ─────────
    import json as _json
    xhr_summary = []
    xhr_budget = 15000
    for xhr in captured_xhrs[:5]:
        xhr_text = _json.dumps({
            "url": xhr["url"],
            "json": xhr["json"],
        }, indent=2, default=str)
        if len(xhr_text) > xhr_budget:
            xhr_text = xhr_text[:xhr_budget] + "\n... (truncated)"
        xhr_summary.append(xhr_text)
    xhr_block = "\n---\n".join(xhr_summary) if xhr_summary else "(no XHRs captured)"

    listing_prompt = _LISTING_PROMPT.format(
        url=listing_url, html=cleaned_listing, xhrs=xhr_block,
    )
    try:
        listing_data = _ask_deepseek(listing_prompt)
    except AnalyzeError:
        raise
    except Exception as e:
        raise AnalyzeError(f"DeepSeek analysis failed: {e}", reason="deepseek_error") from e

    analysis["listing"]["notes"] = listing_data.get("notes", "")

    detected_detail_urls = listing_data.get("detected_detail_urls", []) or []
    if detected_detail_urls:
        detected_detail_urls = [
            urljoin(listing_url, u) if u.startswith("/") else u
            for u in detected_detail_urls
            if u
        ]

    # ─── Step 3: fetch + analyze detail page (if any) ────────
    detail_data: dict = {}
    chosen_detail_url = detail_url or (detected_detail_urls[0] if detected_detail_urls else None)

    if chosen_detail_url:
        try:
            chosen_detail_url = _validate_url(chosen_detail_url)
        except InvalidURLError as e:
            warnings.append(f"Detected detail URL was invalid: {e.message}")
            chosen_detail_url = None

    if chosen_detail_url:
        detail_html, detail_from_browser, detail_err = _fetch_html(chosen_detail_url)
        if detail_err:
            warnings.append(f"Could not fetch detail page ({detail_err}); leaving detail_container_selector empty.")
        else:
            cleaned_detail = _clean_html(detail_html)
            analysis["detail"] = {
                "url": chosen_detail_url,
                "html_size": len(detail_html),
                "cleaned_size": len(cleaned_detail),
                "used_browser": detail_from_browser,
            }
            if detail_from_browser:
                warnings.append("Detail page required browser rendering.")
            detail_prompt = _DETAIL_PROMPT.format(url=chosen_detail_url, html=cleaned_detail)
            try:
                detail_data = _ask_deepseek(detail_prompt)
                analysis["detail"]["notes"] = detail_data.get("notes", "")
            except AnalyzeError as e:
                warnings.append(f"Detail analysis failed: {e.message}")
            except Exception as e:
                warnings.append(f"Detail analysis failed: {e}")

    # ─── Step 4: merge everything into the fields dict ───────
    fields = {
        "name": parsed.netloc.replace("www.", "") or "Website",
        "base_url": origin,
        "scraping_method": listing_data.get("scraping_method", "html"),
        "needs_js": bool(listing_data.get("needs_js", False)),
        "use_browser_fallback": bool(listing_data.get("use_browser_fallback", True)),
        "listing_item_selector": listing_data.get("listing_item_selector", "") or "",
        "position_link_selector": listing_data.get("position_link_selector", "") or "",
        "position_title_selector": listing_data.get("position_title_selector", "") or "",
        "position_company_selector": listing_data.get("position_company_selector", "") or "",
        "pagination_url_pattern": listing_data.get("pagination_url_pattern", "") or "",
        "detail_source": detail_data.get("detail_source", "html"),
        "detail_container_selector": detail_data.get("detail_container_selector", "") or "",
        "api_endpoint": listing_data.get("api_endpoint", "") or "",
        "api_results_key": listing_data.get("api_results_key", "") or "",
        "api_pagination_param": listing_data.get("api_pagination_param", "") or "",
        "api_limit_param": listing_data.get("api_limit_param", "") or "",
    }

    fields.update({
        "max_pages": 10,
        "request_timeout": 30,
        "request_delay": 3.0,
        "max_concurrency": 3,
        "is_active": True,
    })

    if chosen_detail_url and not detail_url:
        fields["_analyzed_detail_url"] = chosen_detail_url

    return {
        "success": True,
        "fields": fields,
        "analysis": analysis,
        "warnings": warnings,
    }