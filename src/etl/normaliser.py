"""Normalisation helpers for messy Excel data.

Two functions live here:
- normalize_year(): turns messy financial-year labels into 'YYYY-MM'
- normalize_ticker(): cleans up NSE ticker casing/whitespace
"""

import re

# Map month names/abbreviations to their two-digit number.
_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def normalize_year(raw_year: str) -> str | None:
    """Convert a messy financial-year label into 'YYYY-MM' format.

    Handles: 'Mar-23', 'Mar 23', 'March-2023', '2023', 'FY23',
    'Dec-22', already-clean '2023-03'. Returns None if unparseable.
    """
    if raw_year is None:
        return None

    text = str(raw_year).strip()

    # Case 1: already in the target format, e.g. '2023-03'
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return text

    # Case 2: bare 4-digit year, e.g. '2023' -> assume March FY-end
    if re.fullmatch(r"\d{4}", text):
        return f"{text}-03"

    # Case 3: 'FY23' or 'FY2023' -> strip prefix, treat as bare year
    fy_match = re.fullmatch(r"(?i)FY\s*(\d{2,4})", text)
    if fy_match:
        digits = fy_match.group(1)
        year = f"20{digits}" if len(digits) == 2 else digits
        return f"{year}-03"

    # Case 4: 'Mon-YY', 'Mon YY', 'Month-YYYY', etc.
    # Normalise separators (space or hyphen) then split into month + year parts.
    month_year_match = re.fullmatch(
        r"(?i)([A-Za-z]+)[\s\-]+(\d{2,4})", text
    )
    if month_year_match:
        month_raw, year_raw = month_year_match.groups()
        month_num = _MONTH_MAP.get(month_raw.lower())
        if month_num is None:
            return None  # unrecognised month name
        year = f"20{year_raw}" if len(year_raw) == 2 else year_raw
        return f"{year}-{month_num}"

    # Nothing matched -> unparseable, caller should log and reject the row
    return None


def normalize_ticker(raw_ticker: str) -> str | None:
    """Clean an NSE ticker: strip whitespace, force uppercase.

    Handles: 'tcs' -> 'TCS', ' TCS ' -> 'TCS', 'BAJAJ-AUTO' -> 'BAJAJ-AUTO'
    (hyphens/ampersands preserved, they're valid NSE ticker characters).
    Returns None for empty/missing input.
    """
    if raw_ticker is None:
        return None

    cleaned = str(raw_ticker).strip().upper()

    if not cleaned:
        return None

    return cleaned