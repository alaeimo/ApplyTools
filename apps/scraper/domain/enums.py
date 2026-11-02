"""Domain enums — single source of truth for status & method values."""
from __future__ import annotations

from enum import Enum


class ScrapingMethod(str, Enum):
    """How to discover listings on the site."""
    HTML = "html"        # Static HTML, parse with CSS selectors
    API = "api"          # JSON API endpoint
    JSONLD = "jsonld"    # schema.org JobPosting in <script> tags
    BROWSER = "browser"  # JS-rendered SPA


class DetailSource(str, Enum):
    """Where the detail body comes from."""
    HTML = "html"
    API = "api"
    JSONLD = "jsonld"


class PositionStatus(str, Enum):
    NEW = "new"
    SCRAPED = "scraped"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class FetchMode(str, Enum):
    HTTP = "http"
    BROWSER = "browser"
    AUTO = "auto"   # try HTTP, fall back to browser on challenge
