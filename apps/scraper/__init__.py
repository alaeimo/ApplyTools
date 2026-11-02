"""Scraper package — async, testable, pluggable PhD position scraper.

Layers (top → bottom):
    orchestrator/  — ties everything together, async generator
    pipeline/      — DB persistence with dedup
    extractors/    — pure data extraction (JSON-LD, JMESPath, CSS)
    pagination/    — URL construction strategies
    fetchers/      — HTTP + browser I/O (curl_cffi, Playwright)
    middleware/    — retry, rate limit, headers, proxy
    parsers/       — pure utility functions (URL, text)
    domain/        — Pydantic data contracts
    services/      — bridges Django Website model → SiteConfig
"""
