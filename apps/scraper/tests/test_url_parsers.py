"""Tests for URL parsers — pure functions, instant."""
from scraper.parsers.url import absolute_url, same_host, drop_fragment


class TestAbsoluteUrl:
    def test_absolute_url_returned_as_is(self):
        assert absolute_url("https://a.com/x", "https://b.com/y") == "https://b.com/y"

    def test_relative_url_joined(self):
        assert absolute_url("https://a.com/x/", "y") == "https://a.com/x/y"

    def test_absolute_path_joined_to_host(self):
        # The original buggy join_url() stripped the leading slash and corrupted this
        assert absolute_url("https://a.com/x/", "/y") == "https://a.com/y"

    def test_protocol_relative(self):
        assert absolute_url("https://a.com/", "//cdn.com/z") == "https://cdn.com/z"

    def test_parent_relative(self):
        assert absolute_url("https://a.com/x/y/z", "../../w") == "https://a.com/w"

    def test_empty_href_returns_base(self):
        assert absolute_url("https://a.com/x", "") == "https://a.com/x"

    def test_anchor_only(self):
        # Just a fragment — urljoin keeps it on the current URL
        assert absolute_url("https://a.com/x", "#section") == "https://a.com/x#section"


class TestSameHost:
    def test_same(self):
        assert same_host("https://a.com/x", "https://a.com/y")

    def test_different(self):
        assert not same_host("https://a.com/x", "https://b.com/y")

    def test_with_port(self):
        assert same_host("https://a.com:443/x", "https://a.com/y")


class TestDropFragment:
    def test_strips_fragment(self):
        assert drop_fragment("https://a.com/x#section") == "https://a.com/x"

    def test_no_fragment_unchanged(self):
        assert drop_fragment("https://a.com/x") == "https://a.com/x"
