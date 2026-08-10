"""
Websites Services Package

This package contains services for:
- Extracting position links from listing pages
- Extracting position details from individual pages
- Complete scraping workflow with orchestration
"""

from .scraper import (
    PositionLinkExtractor,
    PositionDetailExtractor,
    PositionScraper,
    ScrapeOrchestrator
)

__all__ = [
    'PositionLinkExtractor',
    'PositionDetailExtractor',
    'PositionScraper',
    'ScrapeOrchestrator',
]

__version__ = '1.0.0'
__description__ = 'Website scraping services for position extraction'