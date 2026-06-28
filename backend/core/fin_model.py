"""
Financial Model engine — Phase 1 of the "Financial Model" branch on L1 (Financial)
of an Org's 6 LeGS tree.

Pure, side-effect-free calculators. Given a set of assumptions + a projection
horizon it builds a 3-statement model (P&L, Balance Sheet, Cash Flow), the key
financial ratios (incl. DSCR), and an FCFF-DCF valuation (Enterprise Value,
Equity Value, Per-Share Price). All money is kept in ABSOLUTE units; the UI
formats to Lakhs/Crores at display time.

Target audience = startup founders at any stage (pre-revenue → 2 yrs of actuals),
so every opening balance is optional and defaults to 0.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DAYS = 365.0


def _num(v, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _series(val: Any, n: int, default: float = 0.0) -> List[float]:
    """Coerce an assumption to a list of length n.
    - list  -> padded/truncated (last value repeats when padding)
    - scalar-> repeated n times
    """
    if isinstance(val, (list, tuple)):
        out = [_num(x, default) for x in val][:n]
        if not out:
            return [float(default)] * n
        while len(out) < n:
            out.append(out[-1])
        return out
    return [_num(val, default)] * n


def _r(x: float, p: int = 2) -> float:
    try:
        return round(float(x), p)
    except (TypeError, ValueError):
        return 0.0


def default_assumptions() -> Dict[str, Any]:
    """A sensible starter the UI can prefill."""
    return {
        # ── Revenue (primary driver) ──
        "revenue_by_year": [10_000_000, 18_000_000, 30_000_000, 46_000_000, 65_000_000],
        # alt quick-fill (used only when revenue_by_year is empty)
        "year1_revenue": 10_000_000,
        "revenue_growth_pct": 60,
        # ── Margins / costs (% of revenue) ──
        "gross_margin_pct": 55,
        "opex_pct": 35,                 # SG&A + other operating, % of revenue
        "other_income_pct": 0,
        # ── Fixed assets / depreciation ──
        "opening_gross_block": 3_000_000,
        "capex_by_year": [2_000_000, 2_000_000, 2_000_000, 2_000_000, 3_000_000],
        "depreciation_pct": 15,         # % of gross block p.a.
        # ── Working capital (days) ──
        "debtor_days": 45,
        "inventory_days": 30,
        "creditor_days": 40,
        "opening_debtors": 0,
        "opening_inventory": 0,
        "opening_creditors": 0,
        # ── Debt ──
        "opening_debt": 2_000_000,
        "interest_rate_pct": 12,
        "new_debt_by_year": [0, 0, 0, 0, 0],
        "repayment_by_year": [400_000, 400_000, 400_000, 400_000, 400_000],
        # ── Equity (opening_reserves is auto-derived as the BS balancing figure) ──
        "opening_equity_capital": 8_000_000,
        "opening_cash": 7_000_000,
        "new_equity_by_year": [0, 0, 0, 0, 0],
        "shares_outstanding": 800_000,
        # ── Tax & dividend ──
        "tax_rate_pct": 25,
        "dividend_payout_pct": 0,       # startups retain everything by default
        # ── Valuation ──
        "wacc_pct": 18,
        "terminal_growth_pct": 4,
    }


def compute_model(assumptions: Dict[str, Any], projection_years: int = 5,
                  year_labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build the full 3-statement model + ratios + DCF valuation."""
    n = max(1, min(int(projection_years or 5), 10))
    a = assumptions or {}

    # ── Revenue ──
    rev_in = a.get("revenue_by_year") or []
    rev_in = [_num(x) for x in rev_in if x not in (None, "")]
    if rev_in:
        revenue = _series(rev_in, n)
    else:  # quick-fill from year1 + growth
        y1 = _num(a.get("year1_revenue"), 0)
        g = _num(a.get("revenue_growth_pct"), 0) / 100.0
        revenue = [y1 * ((1 + g) ** i) for i in range(n)]

    gm = _num(a.get("gross_margin_pct"), 0) / 100.0
    opex_pct = _num(a.get("opex_pct"), 0) / 100.0
    oi_pct = _num(a.get("other_income_pct"), 0) / 100.0
    dep_pct = _num(a.get("depreciation_pct"), 0) / 100.0
    tax_rate = _num(a.get("tax_rate_pct"), 0) / 100.0
    int_rate = _num(a.get("interest_rate_pct"), 0) / 100.0
    div_payout = _num(a.get("dividend_payout_pct"), 0) / 100.0

    capex = _series(a.get("capex_by_year"), n)
    new_debt = _series(a.get("new_debt_by_year"), n)
    repay = _series(a.get("repayment_by_year"), n)
    new_equity = _series(a.get("new_equity_by_year"), n)

    debtor_days = _num(a.get("debtor_days"))
    inv_days = _num(a.get("inventory_days"))
    cred_days = _num(a.get("creditor_days"))

    # Opening balances (historical base — any startup stage)
    open_gross_block = _num(a.get("opening_gross_block"))
    open_debt = _num(a.get("opening_debt"))
    open_equity_cap = _num(a.get("opening_equity_capital"))
    open_reserves = _num(a.get("opening_reserves"))
    open_cash = _num(a.get("opening_cash"))
    open_debtors = _num(a.get("opening_debtors"))
    open_inventory = _num(a.get("opening_inventory"))
    open_creditors = _num(a.get("opening_creditors"))
    shares = _num(a.get("shares_outstanding"), 1) or 1

    # ── P&L ──
    cogs, gross_profit, other_income, opex, ebitda = [], [], [], [], []
    depreciation, ebit, interest, pbt, tax, pat, dividend, retained = [], [], [], [], [], [], [], []
    # Balance sheet roll-forwards
    gross_block, acc_dep, net_block = [], [], []
    inventory, debtors, creditors, debt, cash = [], [], [], [], []
    equity_cap, reserves, net_worth = [], [], []
    tca, total_assets, tcl, total_liab, bs_check = [], [], [], [], []
    # Cash flow
    cfo, cfi, cff, net_change, opening_cash_l, closing_cash_l = [], [], [], [], [], []

    prev_gross_block = open_gross_block
    prev_acc_dep = 0.0
    prev_debt = open_debt
    prev_reserves = open_reserves
    prev_cash = open_cash
    prev_debtors = open_debtors
    prev_inventory = open_inventory
    prev_creditors = open_creditors
    prev_equity_cap = open_equity_cap

    fcff: List[float] = []

    for i in range(n):
        rev = revenue[i]
        c = rev * (1 - gm)
        gp = rev - c
        oi = rev * oi_pct
        ox = rev * opex_pct
        eb = gp + oi - ox  # EBITDA

        gb = prev_gross_block + capex[i]
        dep = gb * dep_pct
        ad = prev_acc_dep + dep
        nb = gb - ad

        e_bit = eb - dep
        d_open = prev_debt  # interest on opening debt for the year
        intr = d_open * int_rate
        p_bt = e_bit - intr
        tx = max(0.0, p_bt) * tax_rate
        p_at = p_bt - tx
        div = max(0.0, p_at) * div_payout
        ret = p_at - div

        # Working capital
        dr = rev / DAYS * debtor_days
        iv = c / DAYS * inv_days
        cr = c / DAYS * cred_days
        d_wc = (dr - prev_debtors) + (iv - prev_inventory) - (cr - prev_creditors)

        # Debt roll-forward
        dbt = prev_debt + new_debt[i] - repay[i]
        # Equity roll-forward
        eq_cap = prev_equity_cap + new_equity[i]
        res = prev_reserves + ret

        # Cash flow
        o_cfo = p_at + dep - d_wc
        o_cfi = -capex[i]
        o_cff = new_debt[i] - repay[i] + new_equity[i] - div
        nc = o_cfo + o_cfi + o_cff
        clo_cash = prev_cash + nc

        # Balance sheet
        cur_assets = iv + dr + clo_cash
        tot_assets = nb + cur_assets
        cur_liab = cr  # short-term operating (bank WC limit modelled in CMA phase)
        net_w = eq_cap + res
        tot_liab = net_w + dbt + cur_liab

        # FCFF = EBIT*(1-tax) + Dep - Capex - ΔWC
        f = e_bit * (1 - tax_rate) + dep - capex[i] - d_wc

        # push
        cogs.append(c); gross_profit.append(gp); other_income.append(oi)
        opex.append(ox); ebitda.append(eb); depreciation.append(dep)
        ebit.append(e_bit); interest.append(intr); pbt.append(p_bt)
        tax.append(tx); pat.append(p_at); dividend.append(div); retained.append(ret)
        gross_block.append(gb); acc_dep.append(ad); net_block.append(nb)
        inventory.append(iv); debtors.append(dr); creditors.append(cr)
        debt.append(dbt); cash.append(clo_cash)
        equity_cap.append(eq_cap); reserves.append(res); net_worth.append(net_w)
        tca.append(cur_assets); total_assets.append(tot_assets)
        tcl.append(cur_liab); total_liab.append(tot_liab); bs_check.append(tot_assets - tot_liab)
        cfo.append(o_cfo); cfi.append(o_cfi); cff.append(o_cff)
        net_change.append(nc); opening_cash_l.append(prev_cash); closing_cash_l.append(clo_cash)
        fcff.append(f)

        # advance
        prev_gross_block = gb; prev_acc_dep = ad; prev_debt = dbt
        prev_reserves = res; prev_cash = clo_cash; prev_equity_cap = eq_cap
        prev_debtors = dr; prev_inventory = iv; prev_creditors = cr

    # ── Ratios ──
    def _safe(num, den):
        return (num / den) if den else 0.0

    current_ratio, quick_ratio, debt_equity, interest_cov, dscr = [], [], [], [], []
    gm_l, ebitda_m, net_m, roce_l, roe_l = [], [], [], [], []
    for i in range(n):
        current_ratio.append(_safe(tca[i], tcl[i] + min(repay[i], debt[i])))
        quick_ratio.append(_safe(tca[i] - inventory[i], tcl[i] + min(repay[i], debt[i])))
        debt_equity.append(_safe(debt[i], net_worth[i]))
        interest_cov.append(_safe(ebitda[i], interest[i]))
        dscr.append(_safe(pat[i] + depreciation[i] + interest[i], interest[i] + repay[i]))
        gm_l.append(_safe(gross_profit[i], revenue[i]) * 100)
        ebitda_m.append(_safe(ebitda[i], revenue[i]) * 100)
        net_m.append(_safe(pat[i], revenue[i]) * 100)
        roce_l.append(_safe(ebit[i], net_worth[i] + debt[i]) * 100)
        roe_l.append(_safe(pat[i], net_worth[i]) * 100)

    dscr_vals = [d for d in dscr if d > 0]
    dscr_avg = sum(dscr_vals) / len(dscr_vals) if dscr_vals else 0.0

    # ── DCF valuation (FCFF) ──
    wacc = _num(a.get("wacc_pct"), 0) / 100.0
    tg = _num(a.get("terminal_growth_pct"), 0) / 100.0
    pv_fcff = []
    for i in range(n):
        disc = (1 + wacc) ** (i + 1) if wacc > -1 else 1.0
        pv_fcff.append(fcff[i] / disc if disc else 0.0)
    sum_pv = sum(pv_fcff)
    if wacc > tg and n >= 1:
        terminal_value = fcff[-1] * (1 + tg) / (wacc - tg)
    else:
        terminal_value = 0.0
    pv_terminal = terminal_value / ((1 + wacc) ** n) if wacc > -1 else 0.0
    enterprise_value = sum_pv + pv_terminal
    net_debt = open_debt - open_cash
    equity_value = enterprise_value - net_debt
    per_share = equity_value / shares if shares else 0.0

    rnd = lambda lst: [_r(x) for x in lst]  # noqa: E731
    rnd2 = lambda lst: [_r(x, 2) for x in lst]  # noqa: E731

    return {
        "projection_years": n,
        "year_labels": year_labels or [f"Year {i + 1}" for i in range(n)],
        "pnl": {
            "revenue": rnd(revenue), "cogs": rnd(cogs), "gross_profit": rnd(gross_profit),
            "other_income": rnd(other_income), "opex": rnd(opex), "ebitda": rnd(ebitda),
            "depreciation": rnd(depreciation), "ebit": rnd(ebit), "interest": rnd(interest),
            "pbt": rnd(pbt), "tax": rnd(tax), "pat": rnd(pat),
            "dividend": rnd(dividend), "retained": rnd(retained),
        },
        "balance_sheet": {
            "gross_block": rnd(gross_block), "acc_depreciation": rnd(acc_dep), "net_block": rnd(net_block),
            "inventory": rnd(inventory), "debtors": rnd(debtors), "cash": rnd(cash),
            "total_current_assets": rnd(tca), "total_assets": rnd(total_assets),
            "equity_capital": rnd(equity_cap), "reserves": rnd(reserves), "net_worth": rnd(net_worth),
            "debt": rnd(debt), "creditors": rnd(creditors), "total_current_liabilities": rnd(tcl),
            "total_liabilities": rnd(total_liab), "balance_check": rnd(bs_check),
        },
        "cash_flow": {
            "cfo": rnd(cfo), "cfi": rnd(cfi), "cff": rnd(cff), "net_change": rnd(net_change),
            "opening_cash": rnd(opening_cash_l), "closing_cash": rnd(closing_cash_l),
        },
        "ratios": {
            "current_ratio": rnd2(current_ratio), "quick_ratio": rnd2(quick_ratio),
            "debt_equity": rnd2(debt_equity), "interest_coverage": rnd2(interest_cov),
            "dscr": rnd2(dscr), "gross_margin_pct": rnd2(gm_l), "ebitda_margin_pct": rnd2(ebitda_m),
            "net_margin_pct": rnd2(net_m), "roce_pct": rnd2(roce_l), "roe_pct": rnd2(roe_l),
            "debtor_days": [_r(debtor_days, 0)] * n, "inventory_days": [_r(inv_days, 0)] * n,
            "creditor_days": [_r(cred_days, 0)] * n,
        },
        "valuation": {
            "fcff": rnd(fcff), "pv_fcff": rnd(pv_fcff), "sum_pv_fcff": _r(sum_pv),
            "terminal_value": _r(terminal_value), "pv_terminal": _r(pv_terminal),
            "enterprise_value": _r(enterprise_value), "net_debt": _r(net_debt),
            "equity_value": _r(equity_value), "per_share": _r(per_share, 2),
            "wacc_pct": _r(wacc * 100, 2), "terminal_growth_pct": _r(tg * 100, 2),
        },
        "summary": {
            "dscr_avg": _r(dscr_avg, 2),
            "revenue_cagr_pct": _r(((revenue[-1] / revenue[0]) ** (1 / max(1, n - 1)) - 1) * 100, 2)
            if n > 1 and revenue[0] > 0 else 0.0,
            "final_year_pat": _r(pat[-1]),
            "min_dscr": _r(min(dscr_vals), 2) if dscr_vals else 0.0,
        },
    }
