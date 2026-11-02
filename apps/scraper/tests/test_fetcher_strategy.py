"""Tests for the AutoFetcher's challenge detection logic.

We don't actually make HTTP calls — we mock the inner HttpFetcher/BrowserFetcher
to verify the strategy selects the right one.
"""
import pytest

from scraper.domain.models import FetchResult
from scraper.fetchers.factory import _looks_like_challenge


def _make_result(status: int, body: bytes, content_type="text/html") -> FetchResult:
    return FetchResult(
        url="https://example.com",
        status=status,
        headers={"content-type": content_type},
        body_bytes=body,
        elapsed_ms=10.0,
    )


class TestChallengeDetection:
    def test_cloudflare_503_detected(self):
        body = b"<html><title>Just a moment...</title>cloudflare ray id: abc</html>"
        assert _looks_like_challenge(_make_result(503, body))

    def test_datadome_403_detected(self):
        body = b"<html><body>datadome captcha</body></html>"
        assert _looks_like_challenge(_make_result(403, body))

    def test_normal_403_not_detected(self):
        # A normal 403 (e.g. wrong auth) should NOT trigger browser fallback
        body = b"<html><body>Not Found</body></html>"
        assert not _looks_like_challenge(_make_result(403, body))

    def test_200_not_detected(self):
        body = b"<html><body>normal content</body></html>"
        assert not _looks_like_challenge(_make_result(200, body))

    def test_500_not_detected(self):
        body = b"Internal Server Error"
        assert not _looks_like_challenge(_make_result(500, body))
