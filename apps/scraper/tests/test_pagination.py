"""Tests for pagination strategies — pure sync functions, no I/O."""
from scraper.domain.models import PaginationConfig, SiteConfig
from scraper.pagination.strategies import (
    PageStrategy,
    OffsetStrategy,
    CursorStrategy,
    LinkStrategy,
    make_strategy,
)


def _config(max_pages=3):
    return SiteConfig(name="t", base_url="https://x.com", max_pages=max_pages)


class TestPageStrategy:
    def test_increments_page(self):
        s = PageStrategy(PaginationConfig(type="page", param="page",
                                          limit_param="limit", limit_value=10))
        url = s.next_url("https://x.com/jobs?page=1&limit=10", 1, None, _config())
        assert url == "https://x.com/jobs?page=2&limit=10"

    def test_stops_at_max_pages(self):
        s = PageStrategy(PaginationConfig(type="page", param="page"))
        assert s.next_url("https://x.com/jobs?page=3", 3, None, _config(max_pages=3)) is None

    def test_preserves_other_query_params(self):
        s = PageStrategy(PaginationConfig(type="page", param="page"))
        url = s.next_url("https://x.com/jobs?sort=date&page=1", 1, None, _config())
        assert "sort=date" in url and "page=2" in url


class TestOffsetStrategy:
    def test_increments_offset(self):
        s = OffsetStrategy(PaginationConfig(type="offset", param="offset",
                                             limit_param="limit", limit_value=10))
        url = s.next_url("https://x.com/jobs?offset=0&limit=10", 1, None, _config())
        assert "offset=10" in url and "limit=10" in url


class TestCursorStrategy:
    def test_extracts_cursor_from_json(self, make_result):
        result = make_result(
            url="https://api.example.com/jobs?cursor=abc",
            body=b'{"next_cursor": "def"}',
            content_type="application/json",
        )
        s = CursorStrategy(PaginationConfig(type="cursor", param="cursor",
                                            cursor_path="next_cursor"))
        url = s.next_url("https://api.example.com/jobs?cursor=abc", 1, result, _config())
        assert "cursor=def" in url

    def test_returns_none_when_no_cursor(self, make_result):
        result = make_result(
            body=b'{"next_cursor": null}',
            content_type="application/json",
        )
        s = CursorStrategy(PaginationConfig(type="cursor", param="cursor",
                                            cursor_path="next_cursor"))
        assert s.next_url("https://x.com", 1, result, _config()) is None


class TestLinkStrategy:
    def test_extracts_next_link(self, make_result, listing_html):
        result = make_result(
            url="https://example.com/jobs?page=1",
            body=listing_html.encode(),
            content_type="text/html; charset=utf-8",
        )
        s = LinkStrategy(PaginationConfig(type="link"))
        url = s.next_url("https://example.com/jobs?page=1", 1, result, _config())
        assert url == "https://example.com/jobs?page=2"

    def test_returns_none_when_no_next(self, make_result):
        result = make_result(body=b"<html><body>no link</body></html>",
                              content_type="text/html")
        s = LinkStrategy(PaginationConfig(type="link"))
        assert s.next_url("https://x.com", 1, result, _config()) is None


class TestFactory:
    def test_dispatch(self):
        assert isinstance(make_strategy(PaginationConfig(type="page", param="page")),
                          PageStrategy)
        assert isinstance(make_strategy(PaginationConfig(type="offset", param="offset")),
                          OffsetStrategy)
        assert isinstance(make_strategy(PaginationConfig(type="cursor", param="cursor",
                                                         cursor_path="x")), CursorStrategy)
        assert isinstance(make_strategy(PaginationConfig(type="link")), LinkStrategy)
        assert make_strategy(None) is None
