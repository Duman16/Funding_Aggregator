import pytest
from datetime import date
from app.processor.cleaner import (
    clean_html, clean_title, extract_keywords,
    parse_date, parse_amount, normalize_status,
)


class TestCleanHtml:
    def test_removes_tags(self):
        assert clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self):
        assert clean_html("AT&amp;T &lt;Corp&gt;") == "AT&T <Corp>"

    def test_normalizes_whitespace(self):
        assert clean_html("  too   many   spaces  ") == "too many spaces"

    def test_none_input(self):
        assert clean_html(None) is None

    def test_empty_string(self):
        assert clean_html("") is None


class TestCleanTitle:
    def test_basic(self):
        assert clean_title("Research Grant for Science") == "Research Grant for Science"

    def test_strips_punctuation(self):
        assert clean_title("Grant Title.") == "Grant Title"

    def test_truncates(self):
        long = "A" * 600
        result = clean_title(long)
        assert len(result) <= 500

    def test_none(self):
        assert clean_title(None) is None


class TestExtractKeywords:
    def test_returns_list(self):
        result = extract_keywords("research funding science technology health")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_filters_stop_words(self):
        result = extract_keywords("the and or but for of with")
        assert "the" not in result
        assert "and" not in result

    def test_max_keywords(self):
        text = " ".join([f"word{i}" * 3 for i in range(50)])
        result = extract_keywords(text, max_keywords=5)
        assert len(result) <= 5

    def test_none_input(self):
        assert extract_keywords(None) == []

    def test_domain_boosting(self):
        result = extract_keywords("research grant health funding science")
        # Domain words should appear near the top
        domain_words = {"research", "grant", "health", "funding", "science"}
        top_3 = set(result[:3])
        assert len(top_3 & domain_words) > 0


class TestParseDate:
    def test_slash_format(self):
        assert parse_date("01/15/2025") == date(2025, 1, 15)

    def test_iso_format(self):
        assert parse_date("2025-06-30") == date(2025, 6, 30)

    def test_date_passthrough(self):
        d = date(2025, 3, 1)
        assert parse_date(d) == d

    def test_none_input(self):
        assert parse_date(None) is None

    def test_invalid_string(self):
        assert parse_date("not-a-date") is None


class TestParseAmount:
    def test_integer(self):
        assert parse_amount(500000) == 500000.0

    def test_string_with_comma(self):
        assert parse_amount("1,000,000") == 1000000.0

    def test_zero_returns_none(self):
        assert parse_amount(0) is None

    def test_none(self):
        assert parse_amount(None) is None

    def test_invalid(self):
        assert parse_amount("N/A") is None


class TestNormalizeStatus:
    def test_posted_to_open(self):
        assert normalize_status("Posted") == "open"

    def test_forecasted(self):
        assert normalize_status("Forecasted") == "forecasted"

    def test_closed(self):
        assert normalize_status("Archived") == "closed"

    def test_none(self):
        assert normalize_status(None) == "unknown"
