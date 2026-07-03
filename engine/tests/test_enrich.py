"""Tests for the regex-first detail parser (the Claude-cost saver)."""
from dealscanner_engine.enrich import regex_financials, _money


def test_money_units():
    assert _money("2.4", "M") == 2_400_000
    assert _money("420", "K") == 420_000
    assert _money("1,200,000", None) == 1_200_000
    assert _money("3.1", "million") == 3_100_000


def test_regex_pulls_all_four_labelled_figures():
    md = "Asking Price: $2.4M   Gross Revenue: $6,690,000   Adjusted EBITDA: $1.95M   Cash Flow: $850K"
    r = regex_financials(md)
    assert r == {"asking_price": 2_400_000, "revenue": 6_690_000,
                 "ebitda": 1_950_000, "sde": 850_000}


def test_regex_partial_omits_absent_fields():
    md = "List Price $1,200,000 | TTM Revenue $3.1 million | SDE $420,000"
    r = regex_financials(md)
    assert r["asking_price"] == 1_200_000 and r["revenue"] == 3_100_000 and r["sde"] == 420_000
    assert "ebitda" not in r          # no EBITDA on the page -> not invented


def test_regex_empty_when_no_figures():
    assert regex_financials("A lovely business with great upside and no numbers shown") == {}
