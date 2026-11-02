"""HTML→text conversion. Uses trafilatura for substantial content, fast regex
for tiny fragments (titles, company names, etc.)."""
from __future__ import annotations

import re
from html import unescape

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Convert HTML fragment/document to clean plain text.

    Strategy:
      - Empty/None           → ""
      - No '<' (plain text) → strip + unescape
      - Short (<500 chars)  → fast regex strip (titles, names)
      - Long                → trafilatura (handles boilerplate, tables, lists)
    """
    if not html or not isinstance(html, str):
        return ""
    if "<" not in html:
        return _WS_RE.sub(" ", unescape(html)).strip()
    if len(html) < 500:
        text = unescape(_TAG_RE.sub(" ", html))
        return _WS_RE.sub(" ", text).strip()
    if _HAS_TRAFILATURA:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        return (text or "").strip()
    # Fallback if trafilatura not installed
    text = unescape(_TAG_RE.sub(" ", html))
    return _WS_RE.sub(" ", text).strip()
