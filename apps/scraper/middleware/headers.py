"""Browser-like header set with UA rotation. Fixes the original code's wrong
'Accept: application/json' on HTML pages."""
from __future__ import annotations

import random

# Real Chrome 124 user-agents on Win/Mac/Linux — picked at random per request
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def build_browser_headers(
    *,
    accept: str | None = None,
    referer: str | None = None,
    extra: dict | None = None,
    is_html: bool = True,
) -> dict[str, str]:
    """Build a header set that mirrors real Chrome traffic.

    The original scraper sent `Accept: application/json, text/plain, */*` for
    HTML pages — a trivial bot signal. This corrects that.
    """
    if accept is None:
        accept = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
            if is_html
            else "application/json, text/plain, */*"
        )
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9,de;q=0.7,fr;q=0.6",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Fetch-Dest": "document" if is_html else "empty",
        "Sec-Fetch-Mode": "navigate" if is_html else "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1" if is_html else "?0",
        "Upgrade-Insecure-Requests": "1" if is_html else "0",
    }
    if referer:
        headers["Referer"] = referer
    if extra:
        headers.update(extra)
    return headers
