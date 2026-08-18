"""Tests for the tearsheet PDF generator -- mostly the text-truncation
safety net (spec R-08 mitigation) since the chart/layout logic is best
verified by actually rendering a PDF (done manually during development,
see the module docstring's note on the Rs./₹ font bug and the ROCE-trend
chart fix, both found by rendering and looking, not by review).

Run with: pytest tests/reports/test_tearsheet.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "reports"))

from tearsheet import _truncate, MAX_CELL_CHARS


def test_truncate_leaves_short_text_unchanged():
    assert _truncate("Short pro text.") == "Short pro text."


def test_truncate_cuts_long_text_with_ellipsis():
    long_text = "A" * 300
    result = _truncate(long_text)
    assert len(result) == MAX_CELL_CHARS
    assert result.endswith("…")


def test_truncate_handles_exact_boundary():
    exact_text = "A" * MAX_CELL_CHARS
    assert _truncate(exact_text) == exact_text  # exactly at the limit -- no truncation needed


def test_truncate_handles_one_over_boundary():
    text = "A" * (MAX_CELL_CHARS + 1)
    result = _truncate(text)
    assert len(result) == MAX_CELL_CHARS
    assert result.endswith("…")
