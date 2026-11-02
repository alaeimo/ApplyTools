"""Tests for HTML→text parser."""
from scraper.parsers.text import html_to_text


class TestHtmlToText:
    def test_empty(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_plain_text(self):
        assert html_to_text("Hello, world") == "Hello, world"

    def test_short_fragment(self):
        assert html_to_text("<b>Hello</b>") == "Hello"

    def test_unescapes_entities(self):
        assert html_to_text("Tom &amp; Jerry") == "Tom & Jerry"

    def test_strips_tags_in_short_html(self):
        text = html_to_text("<p>Hello <b>world</b></p>")
        assert "Hello" in text and "world" in text

    def test_long_html_uses_trafilatura(self):
        html = "<html><body>" + ("<p>paragraph of substantial content here.</p>" * 50) + "</body></html>"
        text = html_to_text(html)
        assert "paragraph" in text
