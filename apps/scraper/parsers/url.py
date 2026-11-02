"""URL helpers — robust joining + normalization for dedup."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode


def absolute_url(base: str, href: str) -> str:
    """Robust URL join that handles all real-world href formats.

    Cases handled:
      - absolute URL ("https://other.com/x")      → returned as-is
      - protocol-relative ("//cdn.com/y")         → inherits base scheme
      - absolute-path ("/path")                   → joins to base host
      - relative ("path" or "../path")             → urljoin handles
      - empty string                                → returns base

    Replaces the buggy join_url() in the original code which stripped leading
    slashes and forced trailing slashes on the base.
    """
    if not href:
        return base
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        scheme = urlparse(base).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base, href)


def same_host(url_a: str, url_b: str) -> bool:
    """Check if two URLs share the same host (for in-scope link filtering).
    Normalizes default ports so https://a.com:443 and https://a.com match."""
    host_a = _normalize_host(urlparse(url_a))
    host_b = _normalize_host(urlparse(url_b))
    return host_a == host_b


def _normalize_host(p) -> str:
    netloc = p.netloc.lower()
    if p.scheme == "https" and netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]
    elif p.scheme == "http" and netloc.endswith(":80"):
        netloc = netloc.rsplit(":", 1)[0]
    return netloc


def drop_fragment(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))
