"""Unit tests for src/etl/normaliser.py

Run with: pytest tests/etl/test_normalise.py -v
"""

import sys
import os

# Make src/ importable when running pytest from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "etl"))

from normaliser import normalize_year, normalize_ticker


# ---------------------------------------------------------------------------
# normalize_year() — 20 test cases
# ---------------------------------------------------------------------------

def test_year_mar23():
    assert normalize_year("Mar-23") == "2023-03"


def test_year_mar_space_23():
    assert normalize_year("Mar 23") == "2023-03"


def test_year_march_full_hyphen():
    assert normalize_year("March-2023") == "2023-03"


def test_year_march_full_space():
    assert normalize_year("March 2023") == "2023-03"


def test_year_bare_2023():
    assert normalize_year("2023") == "2023-03"


def test_year_bare_2010():
    assert normalize_year("2010") == "2010-03"


def test_year_fy23():
    assert normalize_year("FY23") == "2023-03"


def test_year_fy2023():
    assert normalize_year("FY2023") == "2023-03"


def test_year_fy_lowercase():
    assert normalize_year("fy23") == "2023-03"


def test_year_dec22():
    assert normalize_year("Dec-22") == "2022-12"


def test_year_dec_full_name():
    assert normalize_year("December-2022") == "2022-12"


def test_year_jun23():
    assert normalize_year("Jun-23") == "2023-06"


def test_year_jun_full_name():
    assert normalize_year("June-2023") == "2023-06"


def test_year_already_normalised():
    assert normalize_year("2023-03") == "2023-03"


def test_year_already_normalised_december():
    assert normalize_year("2022-12") == "2022-12"


def test_year_garbage():
    assert normalize_year("garbage") is None


def test_year_empty_string():
    assert normalize_year("") is None


def test_year_none_input():
    assert normalize_year(None) is None


def test_year_unrecognised_month():
    assert normalize_year("Xyz-23") is None


def test_year_lowercase_month():
    assert normalize_year("mar-23") == "2023-03"


# ---------------------------------------------------------------------------
# normalize_ticker() — 15 test cases
# ---------------------------------------------------------------------------

def test_ticker_already_upper():
    assert normalize_ticker("TCS") == "TCS"


def test_ticker_lowercase():
    assert normalize_ticker("tcs") == "TCS"


def test_ticker_mixed_case():
    assert normalize_ticker("Tcs") == "TCS"


def test_ticker_leading_trailing_whitespace():
    assert normalize_ticker(" TCS ") == "TCS"


def test_ticker_leading_whitespace_only():
    assert normalize_ticker("  TCS") == "TCS"


def test_ticker_trailing_whitespace_only():
    assert normalize_ticker("TCS  ") == "TCS"


def test_ticker_hyphenated_preserved():
    assert normalize_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"


def test_ticker_hyphenated_lowercase():
    assert normalize_ticker("bajaj-auto") == "BAJAJ-AUTO"


def test_ticker_ampersand_preserved():
    assert normalize_ticker("M&M") == "M&M"


def test_ticker_ampersand_lowercase():
    assert normalize_ticker("m&m") == "M&M"


def test_ticker_empty_string():
    assert normalize_ticker("") is None


def test_ticker_whitespace_only():
    assert normalize_ticker("   ") is None


def test_ticker_none_input():
    assert normalize_ticker(None) is None


def test_ticker_single_char():
    assert normalize_ticker("i") == "I"


def test_ticker_numeric_suffix():
    assert normalize_ticker("m&m fin") == "M&M FIN"