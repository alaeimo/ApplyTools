"""Pydantic data contracts — the only types that cross module boundaries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


def normalize_url(url: str) -> str:
    """Stable URL form for deduplication.

    - lowercase scheme & host
    - strip default ports (80 for http, 443 for https)
    - sort query parameters (so ?a=1&b=2 == ?b=2&a=1)
    - drop fragment
    - normalize trailing slash on path
    """
    if not url:
        return ""
    p = urlparse(url)
    netloc = p.netloc.lower()
    if p.scheme == "https" and netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]
    elif p.scheme == "http" and netloc.endswith(":80"):
        netloc = netloc.rsplit(":", 1)[0]
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((p.scheme.lower(), netloc, path, "", query, ""))


class PaginationConfig(BaseModel):
    """Declarative pagination spec. Replaces per-site hardcoded logic."""
    type: str = "page"                      # page | offset | cursor | link
    param: str = "page"
    limit_param: Optional[str] = "limit"
    limit_value: int = 10
    cursor_path: Optional[str] = None       # JMESPath into JSON response
    next_link_selector: Optional[str] = None  # CSS selector for <a rel="next">


class SiteConfig(BaseModel):
    """Declarative per-site configuration.

    Replaces the bloated Website model's 15+ selector fields with ~10 declarative ones,
    most of which are optional because extractors auto-detect (JSON-LD first).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    base_url: HttpUrl
    list_url: Optional[str] = None          # if different from base_url

    # --- API mode (mutually exclusive with HTML mode) ---
    api_endpoint: Optional[HttpUrl] = None
    api_method: str = "GET"
    api_headers: dict[str, str] = Field(default_factory=dict)
    api_extra_params: dict[str, Any] = Field(default_factory=dict)
    api_body_template: Optional[str] = None
    api_auth_token: Optional[str] = None
    api_results_jmespath: Optional[str] = None  # e.g. "jobs[*]"
    api_pagination: Optional[PaginationConfig] = None

    # --- HTML mode ---
    needs_js: bool = False
    listing_css: Optional[str] = None
    link_css: Optional[str] = None
    title_css: Optional[str] = None
    company_css: Optional[str] = None
    next_page_css: Optional[str] = None     # alternative to api_pagination

    # --- Detail extraction ---
    detail_api_endpoint: Optional[HttpUrl] = None
    detail_jmespath: Optional[str] = None   # e.g. "data.job"
    detail_container_css: Optional[str] = None

    # --- Behaviour ---
    max_pages: int = 10
    request_timeout: float = 30.0
    request_delay: tuple[float, float] = (1.5, 6.0)  # min/max seconds, randomized
    max_concurrency: int = 5
    use_browser_fallback: bool = True
    respect_robots: bool = True

    # --- Extraction priority (auto-detect if you set it) ---
    extractor_priority: list[str] = Field(
        default_factory=lambda: ["jsonld", "jmespath", "css"]
    )


class FetchResult(BaseModel):
    """Result of fetching a URL. Carries raw bytes so callers decide how to decode."""
    url: str
    status: int
    headers: dict[str, str]
    body_bytes: bytes
    elapsed_ms: float
    from_browser: bool = False
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _charset(self) -> Optional[str]:
        ct = self.headers.get("content-type", "")
        if "charset=" in ct:
            return ct.split("charset=", 1)[1].split(";")[0].strip()
        return None

    @property
    def text(self) -> str:
        try:
            return self.body_bytes.decode(self._charset or "utf-8", errors="replace")
        except Exception:
            return self.body_bytes.decode("utf-8", errors="replace")

    @property
    def is_json(self) -> bool:
        return "json" in self.headers.get("content-type", "").lower()

    @property
    def is_html(self) -> bool:
        return "html" in self.headers.get("content-type", "").lower()

    def json(self) -> Any:
        import json
        return json.loads(self.body_bytes)


class PositionExtracted(BaseModel):
    """A scraped position before persistence. Pure data, no I/O."""
    url: str
    title: str
    company: str = ""
    cleaned_text: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extractor_used: str = ""
    confidence: float = 1.0

    @property
    def normalized_url(self) -> str:
        return normalize_url(self.url)


class ScrapeStats(BaseModel):
    """Final stats from a scrape run."""
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    pages: int = 0
    elapsed_s: float = 0.0
