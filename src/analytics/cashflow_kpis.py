"""Sprint 2 Cash Flow KPIs -- FCF, CFO quality, CapEx intensity, capital allocation.

Cash flow metrics get their own module rather than living in ratios.py
because they answer a different kind of question: ratios.py mostly asks
"is this company profitable/efficient", while these ask "is the reported
profit actually turning into cash, and what is management doing with that
cash" -- the classic "profit is an opinion, cash is a fact" distinction
that's the whole reason cash flow statements exist as a third statement
alongside P&L and balance sheet.
"""

import pandas as pd


def free_cash_flow(operating_activity, investing_activity):
    """FCF = CFO + CFI (spec 13 and 6.4 agree on this formula)."""
    if pd.isna(operating_activity) or pd.isna(investing_activity):
        return None
    return operating_activity + investing_activity


def capex_intensity(investing_activity, sales):
    """CapEx Intensity = abs(investing_activity) / sales x 100.

    investing_activity is used as a CapEx proxy per spec (6.4: "abs(
    investing_activity) -- CapEx proxy"), since there's no dedicated CapEx
    line item in this dataset -- investing_activity also includes
    acquisitions/other investments, so this is explicitly an
    approximation, not a precise CapEx figure.
    """
    if pd.isna(investing_activity) or pd.isna(sales) or sales == 0:
        return None
    return (abs(investing_activity) / sales) * 100


def cfo_quality_score(operating_activity, net_profit):
    """CFO/PAT ratio. >1.0 = high quality earnings; <0.5 = accrual risk (spec 13).

    None if net_profit = 0 -- can't sensibly express "how many times cash
    covers profit" when profit itself is zero; the ratio would be either
    undefined (0 CFO) or infinite (any nonzero CFO), neither useful.
    """
    if pd.isna(operating_activity) or pd.isna(net_profit) or net_profit == 0:
        return None
    return operating_activity / net_profit


def fcf_conversion_rate(fcf, operating_profit):
    """FCF Conversion = FCF / operating_profit x 100. None if operating_profit = 0."""
    if pd.isna(fcf) or pd.isna(operating_profit) or operating_profit == 0:
        return None
    return (fcf / operating_profit) * 100


# ---------------------------------------------------------------------------
# Capital allocation pattern classification
# ---------------------------------------------------------------------------

# The spec names 8 classes (D11: "capital allocation pattern (8 classes)")
# but its KPI reference table (Section 13) only spells out the sign
# pattern and label for 3 of them explicitly: Reinvestor (+,-,-),
# Shareholder Returns (+,-,-, sub-classified from Reinvestor by CFO/PAT>1),
# and Distress (-,?,+). There are exactly 2^3 = 8 possible sign
# combinations of (CFO, CFI, CFF), so the remaining 5 aren't a mystery --
# they're just not named in the spec text. Labelled here using standard
# corporate-finance capital-allocation vocabulary, since the spec doesn't
# supply names for them; this is a genuine judgment call, not something
# taken directly from the document, and worth treating as provisional
# until reviewed.
def classify_capital_allocation(cfo, cfi, cff, net_profit=None) -> str:
    """Classify a company-year's capital allocation pattern from CFO/CFI/CFF signs.

    Returns one of 8 labels. CFO_sign/CFI_sign/CFF_sign are computed
    separately by the caller for the capital_allocation.csv output -- this
    function only needs the raw values to decide the sign combination
    (treating exactly 0 as positive, matching the spec's ">= 0" framing for
    "positive = good" cash flow signals).
    """
    if pd.isna(cfo) or pd.isna(cfi) or pd.isna(cff):
        return "Unknown"

    cfo_pos, cfi_pos, cff_pos = cfo >= 0, cfi >= 0, cff >= 0

    if cfo_pos and not cfi_pos and not cff_pos:
        # Spec's two explicitly-named (+,-,-) patterns are distinguished by
        # earnings quality: high CFO/PAT means genuine reinvestment from
        # strong operations, low means it's more likely just paying down
        # debt/dividends from thin operating cash.
        if net_profit is not None and pd.notna(net_profit) and net_profit != 0 and (cfo / net_profit) > 1.0:
            return "Reinvestor"
        return "Shareholder Returns"
    if not cfo_pos and cff_pos:
        return "Distress"  # spec: (-, ?, +) -- raising funds to cover a CFO shortfall
    if cfo_pos and cfi_pos and cff_pos:
        return "Aggressive Expansion"       # raising capital AND divesting AND operations positive
    if cfo_pos and not cfi_pos and cff_pos:
        return "Growth Financed Externally"  # investing for growth funded by new capital, not just ops
    if cfo_pos and cfi_pos and not cff_pos:
        return "Deleveraging via Divestment"  # selling assets/investments to pay down debt
    if not cfo_pos and not cfi_pos and not cff_pos:
        return "Cash Burn"                   # weak ops, still investing, no external funding -- draining reserves
    if not cfo_pos and cfi_pos and not cff_pos:
        return "Distressed Asset Sale"       # selling assets to fund both weak ops and debt repayment
    return "Unclassified"
