"""Tests for the headers middleware — verifies Accept header correctness."""
from scraper.middleware.headers import build_browser_headers


class TestBuildBrowserHeaders:
    def test_html_default_accept(self):
        h = build_browser_headers(is_html=True)
        assert "text/html" in h["Accept"]
        assert "application/json, text/plain" not in h["Accept"]
        assert h["Sec-Fetch-Dest"] == "document"
        assert h["Sec-Fetch-Mode"] == "navigate"

    def test_json_accept_for_apis(self):
        h = build_browser_headers(is_html=False)
        assert h["Accept"] == "application/json, text/plain, */*"
        assert h["Sec-Fetch-Dest"] == "empty"
        assert h["Sec-Fetch-Mode"] == "cors"

    def test_explicit_accept_overrides(self):
        h = build_browser_headers(accept="application/xml", is_html=True)
        assert h["Accept"] == "application/xml"

    def test_user_agent_rotates(self):
        # Run several times — should hit at least 2 different UAs (probabilistic but
        # almost certain with 3 UAs and 20 draws)
        uas = {build_browser_headers()["User-Agent"] for _ in range(20)}
        assert len(uas) >= 2

    def test_referer_set(self):
        h = build_browser_headers(referer="https://example.com/")
        assert h["Referer"] == "https://example.com/"

    def test_extra_merged(self):
        h = build_browser_headers(extra={"X-Custom": "abc"})
        assert h["X-Custom"] == "abc"
        # Standard headers still present
        assert "User-Agent" in h

    def test_sec_fetch_headers_present(self):
        h = build_browser_headers()
        for key in ("Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site",
                    "Sec-Fetch-User", "Upgrade-Insecure-Requests"):
            assert key in h, f"missing {key}"

    def test_accept_encoding_includes_brotli(self):
        h = build_browser_headers()
        assert "br" in h["Accept-Encoding"]
