"""Tests for URL normalization (dedup)."""
from scraper.domain.models import normalize_url


class TestNormalizeUrl:
    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_strips_default_port(self):
        assert normalize_url("https://example.com:443/x") == "https://example.com/x"
        assert normalize_url("http://example.com:80/x") == "http://example.com/x"

    def test_keeps_non_default_port(self):
        assert normalize_url("https://example.com:8443/x") == "https://example.com:8443/x"

    def test_sorts_query_params(self):
        a = normalize_url("https://example.com/jobs?page=1&sort=date")
        b = normalize_url("https://example.com/jobs?sort=date&page=1")
        assert a == b

    def test_strips_fragment(self):
        assert normalize_url("https://example.com/x#section") == "https://example.com/x"

    def test_normalizes_trailing_slash(self):
        # path /x and /x/ normalize to /x (root stays as /)
        assert normalize_url("https://example.com/x/") == "https://example.com/x"
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_empty(self):
        assert normalize_url("") == ""
