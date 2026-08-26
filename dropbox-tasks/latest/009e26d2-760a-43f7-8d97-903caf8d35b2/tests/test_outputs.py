"""Black-box verifier for the consolidated multi-entity three-statement model.

The program under test reads a manifest JSON from ``os.Args[1]`` that points at
three sibling documents (group, entities, intercompany), joins them by entity id
and period, projects each entity's three statements with a circular interest
solve, computes per-entity coverage covenants, and then consolidates the group
with intercompany eliminations and a controlling / non-controlling interest
split. This module contains an independent Python implementation of that model
and compares the program's complete JSON output to it exactly.
"""

import copy
import json
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

APP_DIR = "/app"


@pytest.fixture(scope="session")
def binary():
    go = shutil.which("go")
    assert go is not None, "the Go toolchain must be available in the image"
    out_path = str(Path(tempfile.mkdtemp()) / "consolidated_model")
    proc = subprocess.run(
        [go, "build", "-o", out_path, "."],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.fail(f"go build failed:\n{proc.stdout}\n{proc.stderr}")
    return out_path


def write_pack(pack, root):
    """Materialize a pack as the four on-disk documents; return manifest path."""
    manifest = {
        "periods": pack["periods"],
        "documents": {
            "group": "group.json",
            "entities": "entities.json",
            "intercompany": "intercompany.json",
        },
    }
    (Path(root) / "group.json").write_text(json.dumps(pack["group"]))
    (Path(root) / "entities.json").write_text(json.dumps({"entities": pack["entities"]}))
    (Path(root) / "intercompany.json").write_text(json.dumps(pack["intercompany"]))
    manifest_path = Path(root) / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return str(manifest_path)


def run_model(binary, pack):
    root = tempfile.mkdtemp()
    manifest_path = write_pack(pack, root)
    proc = subprocess.run(
        [binary, manifest_path], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, (
        f"non-zero exit for {json.dumps(pack, sort_keys=True)}:\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# Integer helpers (must match the Go implementation exactly).
# --------------------------------------------------------------------------- #
def bps(amount, ratio):
    # Applied only to non-negative amounts, so truncation equals floor.
    return amount * ratio // 10_000


def days(amount, day_count):
    return amount * day_count // 365


def floordiv(a, b):
    # Signed floor division; Python's // already floors.
    return a // b


def interest_from_debt(beg_term, end_term, term_rate, beg_rev, end_rev, rev_rate):
    return ((beg_term + end_term) * term_rate) // 20_000 + (
        (beg_rev + end_rev) * rev_rate
    ) // 20_000


# --------------------------------------------------------------------------- #
# Per-entity single-period calculation.
# --------------------------------------------------------------------------- #
def calc_entity_year(group, ent, beg, idx, year, interest, iterations, converged):
    a = ent["assumptions"]
    tax_rate = group["tax_rate_bps"][idx]
    term_rate = group["benchmark_rate_bps"][idx] + a["term_spread_bps"][idx]
    rev_rate = group["benchmark_rate_bps"][idx] + a["revolver_spread_bps"][idx]

    revenue = bps(beg["revenue"], 10_000 + a["revenue_growth_bps"][idx])
    cogs = bps(revenue, a["cogs_pct_revenue_bps"][idx])
    gross = revenue - cogs
    opex = bps(revenue, a["opex_pct_revenue_bps"][idx])
    ebitda = gross - opex
    book_dep = min(
        beg["ppe"], bps(beg["ppe"], a["depreciation_pct_beginning_ppe_bps"][idx])
    )
    tax_dep = min(
        beg["ppe"], bps(beg["ppe"], a["tax_depreciation_pct_beginning_ppe_bps"][idx])
    )
    stock_comp = bps(revenue, a["stock_comp_pct_revenue_bps"][idx])
    ebit = ebitda - book_dep - stock_comp
    pretax = ebit - interest

    book_tax = bps(pretax, tax_rate) if pretax > 0 else 0
    temp_diff = tax_dep - book_dep
    taxable_income = pretax - temp_diff
    current_tax = bps(taxable_income, tax_rate) if taxable_income > 0 else 0
    deferred_tax = book_tax - current_tax
    tax_expense = book_tax
    ni = pretax - tax_expense
    dividends = bps(ni, a["dividend_payout_bps"][idx]) if ni > 0 else 0

    end_ar = days(revenue, a["ar_days"][idx])
    end_inv = days(cogs, a["inventory_days"][idx])
    end_ap = days(cogs, a["ap_days"][idx])
    d_ar = end_ar - beg["ar"]
    d_inv = end_inv - beg["inv"]
    d_ap = end_ap - beg["ap"]
    cfo = ni + book_dep + stock_comp + deferred_tax - d_ar - d_inv + d_ap

    capex = bps(revenue, a["capex_pct_revenue_bps"][idx])
    cfi = -capex
    mandatory = min(beg["term"], bps(beg["term"], a["mandatory_amortization_bps"][idx]))
    min_cash = bps(revenue, a["minimum_cash_pct_revenue_bps"][idx])
    cash_before_financing = beg["cash"] + cfo - capex - dividends - mandatory
    draw = repay = sweep = 0
    term_after_mandatory = beg["term"] - mandatory
    if cash_before_financing < min_cash:
        draw = min_cash - cash_before_financing
    else:
        excess = cash_before_financing - min_cash
        repay = min(beg["rev"], excess)
        excess -= repay
        sweep = min(term_after_mandatory, bps(excess, a["cash_sweep_bps"][idx]))
    end_term = term_after_mandatory - sweep
    end_rev = beg["rev"] + draw - repay
    next_interest = interest_from_debt(
        beg["term"], end_term, term_rate, beg["rev"], end_rev, rev_rate
    )
    cff = -dividends - mandatory - sweep + draw - repay
    net_change_cash = cfo + cfi + cff
    end_cash = beg["cash"] + net_change_cash
    end_ppe = beg["ppe"] + capex - book_dep
    end_dtl = beg["dtl"] + deferred_tax
    end_apic = beg["apic"] + stock_comp
    end_retained = beg["retained"] + ni - dividends

    # Coverage covenants.
    cfads = ebitda - current_tax - capex
    debt_service = mandatory + interest
    dscr_bps = floordiv(cfads * 10_000, debt_service) if debt_service > 0 else 0
    dscr_breach = debt_service > 0 and dscr_bps < group["min_dscr_bps"]
    ending_total_debt = end_term + end_rev
    if idx == 0:
        trailing_ebitda = ebitda
    else:
        trailing_ebitda = floordiv(ebitda + beg["prev_ebitda"], 2)
    leverage_bps = (
        floordiv(ending_total_debt * 10_000, trailing_ebitda)
        if trailing_ebitda > 0
        else 0
    )
    leverage_breach = trailing_ebitda > 0 and leverage_bps > group["max_leverage_bps"]

    bs = {
        "cash_minor": end_cash,
        "accounts_receivable_minor": end_ar,
        "inventory_minor": end_inv,
        "net_ppe_minor": end_ppe,
        "total_assets_minor": end_cash + end_ar + end_inv + end_ppe,
        "accounts_payable_minor": end_ap,
        "deferred_tax_liability_minor": end_dtl,
        "term_debt_minor": end_term,
        "revolver_minor": end_rev,
        "common_stock_minor": beg["common"],
        "additional_paid_in_capital_minor": end_apic,
        "retained_earnings_minor": end_retained,
    }
    bs["total_liabilities_and_equity_minor"] = (
        end_ap + end_dtl + end_term + end_rev + beg["common"] + end_apic + end_retained
    )

    row = {
        "year": year,
        "income_statement": {
            "revenue_minor": revenue,
            "cogs_minor": cogs,
            "gross_profit_minor": gross,
            "opex_minor": opex,
            "ebitda_minor": ebitda,
            "depreciation_minor": book_dep,
            "stock_comp_minor": stock_comp,
            "ebit_minor": ebit,
            "interest_expense_minor": interest,
            "pretax_income_minor": pretax,
            "current_tax_expense_minor": current_tax,
            "deferred_tax_expense_minor": deferred_tax,
            "tax_expense_minor": tax_expense,
            "net_income_minor": ni,
        },
        "tax_schedule": {
            "tax_depreciation_minor": tax_dep,
            "temporary_difference_minor": temp_diff,
            "taxable_income_minor": taxable_income,
            "beginning_dtl_minor": beg["dtl"],
            "deferred_tax_expense_minor": deferred_tax,
            "ending_dtl_minor": end_dtl,
        },
        "working_capital": {
            "accounts_receivable_minor": end_ar,
            "inventory_minor": end_inv,
            "accounts_payable_minor": end_ap,
            "change_ar_minor": d_ar,
            "change_inventory_minor": d_inv,
            "change_ap_minor": d_ap,
        },
        "cash_flow": {
            "net_income_minor": ni,
            "depreciation_minor": book_dep,
            "stock_comp_minor": stock_comp,
            "deferred_tax_minor": deferred_tax,
            "change_ar_minor": d_ar,
            "change_inventory_minor": d_inv,
            "change_ap_minor": d_ap,
            "cfo_minor": cfo,
            "capex_minor": capex,
            "cfi_minor": cfi,
            "dividends_minor": dividends,
            "cff_minor": cff,
            "net_change_cash_minor": net_change_cash,
            "ending_cash_minor": end_cash,
        },
        "debt_schedule": {
            "beginning_term_debt_minor": beg["term"],
            "beginning_revolver_minor": beg["rev"],
            "term_rate_bps": term_rate,
            "revolver_rate_bps": rev_rate,
            "mandatory_amortization_minor": mandatory,
            "cash_sweep_minor": sweep,
            "revolver_draw_minor": draw,
            "revolver_repayment_minor": repay,
            "ending_term_debt_minor": end_term,
            "ending_revolver_minor": end_rev,
            "interest_expense_minor": interest,
            "interest_iterations": iterations,
            "circular_converged": converged,
        },
        "coverage": {
            "cfads_minor": cfads,
            "debt_service_minor": debt_service,
            "dscr_bps": dscr_bps,
            "dscr_breach": dscr_breach,
            "ending_total_debt_minor": ending_total_debt,
            "trailing_ebitda_minor": trailing_ebitda,
            "leverage_bps": leverage_bps,
            "leverage_breach": leverage_breach,
        },
        "balance_sheet": bs,
    }
    row["checks"] = {
        "balance_sheet_check_minor": bs["total_assets_minor"]
        - bs["total_liabilities_and_equity_minor"],
        "cash_reconciliation_check_minor": beg["cash"] + net_change_cash - end_cash,
        "retained_earnings_check_minor": beg["retained"] + ni - dividends - end_retained,
        "ppe_rollforward_check_minor": beg["ppe"] + capex - book_dep - end_ppe,
        "debt_rollforward_check_minor": beg["term"]
        + beg["rev"]
        + draw
        - repay
        - mandatory
        - sweep
        - end_term
        - end_rev,
        "dtl_rollforward_check_minor": beg["dtl"] + deferred_tax - end_dtl,
        "apic_rollforward_check_minor": beg["apic"] + stock_comp - end_apic,
    }
    next_state = {
        "cash": end_cash,
        "ar": end_ar,
        "inv": end_inv,
        "ppe": end_ppe,
        "ap": end_ap,
        "term": end_term,
        "rev": end_rev,
        "common": beg["common"],
        "apic": end_apic,
        "dtl": end_dtl,
        "retained": end_retained,
        "revenue": revenue,
        "prev_ebitda": ebitda,
    }
    return row, next_state, next_interest


def project_entity(group, ent, periods):
    op = ent["opening"]
    st = {
        "cash": op["cash_minor"],
        "ar": op["accounts_receivable_minor"],
        "inv": op["inventory_minor"],
        "ppe": op["net_ppe_minor"],
        "ap": op["accounts_payable_minor"],
        "term": op["term_debt_minor"],
        "rev": op["revolver_minor"],
        "common": op["common_stock_minor"],
        "apic": op["additional_paid_in_capital_minor"],
        "dtl": op["deferred_tax_liability_minor"],
        "retained": op["retained_earnings_minor"],
        "revenue": ent["base_revenue_minor"],
        "prev_ebitda": 0,
    }
    a = ent["assumptions"]
    max_iter = group.get("max_iterations", 100) or 100
    tolerance = group.get("convergence_tolerance_minor", 0)
    rows = []
    for idx, year in enumerate(periods):
        term_rate = group["benchmark_rate_bps"][idx] + a["term_spread_bps"][idx]
        rev_rate = group["benchmark_rate_bps"][idx] + a["revolver_spread_bps"][idx]
        guess = interest_from_debt(
            st["term"], st["term"], term_rate, st["rev"], st["rev"], rev_rate
        )
        converged = False
        iterations = 0
        row = None
        next_state = None
        for iteration in range(1, max_iter + 1):
            row, next_state, next_interest = calc_entity_year(
                group, ent, st, idx, year, guess, iteration, False
            )
            iterations = iteration
            if abs(next_interest - guess) <= tolerance:
                converged = True
                break
            guess = next_interest
        # Report from this same final pass; do not run another pass.
        row["debt_schedule"]["interest_iterations"] = iterations
        row["debt_schedule"]["circular_converged"] = converged
        st = next_state
        rows.append(row)
    return rows


def reference(pack):
    group = pack["group"]
    periods = pack["periods"]
    ico = pack["intercompany"]

    entity_out = []
    entity_rows = {}
    for ent in pack["entities"]:
        rows = project_entity(group, ent, periods)
        entity_rows[ent["id"]] = rows
        entity_out.append(
            {
                "id": ent["id"],
                "kind": ent["kind"],
                "ownership_bps": ent["ownership_bps"],
                "years": rows,
            }
        )

    consolidated = []
    for idx, year in enumerate(periods):
        ico_rev = ico["revenue_minor"][idx]
        ico_trade = ico["trade_balance_minor"][idx]

        def s(section, key):
            return sum(entity_rows[e["id"]][idx][section][key] for e in pack["entities"])

        revenue = s("income_statement", "revenue_minor") - ico_rev
        cogs = s("income_statement", "cogs_minor") - ico_rev
        gross = revenue - cogs
        opex = s("income_statement", "opex_minor")
        ebitda = gross - opex
        dep = s("income_statement", "depreciation_minor")
        stock_comp = s("income_statement", "stock_comp_minor")
        ebit = s("income_statement", "ebit_minor")
        interest = s("income_statement", "interest_expense_minor")
        pretax = s("income_statement", "pretax_income_minor")
        current_tax = s("income_statement", "current_tax_expense_minor")
        deferred_tax = s("income_statement", "deferred_tax_expense_minor")
        tax_expense = s("income_statement", "tax_expense_minor")
        ni = s("income_statement", "net_income_minor")

        minority_ni = 0
        minority_equity = 0
        for e in pack["entities"]:
            own = e["ownership_bps"]
            erow = entity_rows[e["id"]][idx]
            e_ni = erow["income_statement"]["net_income_minor"]
            ebs = erow["balance_sheet"]
            e_equity = (
                ebs["common_stock_minor"]
                + ebs["additional_paid_in_capital_minor"]
                + ebs["retained_earnings_minor"]
            )
            minority_ni += floordiv((10_000 - own) * e_ni, 10_000)
            minority_equity += floordiv((10_000 - own) * e_equity, 10_000)
        controlling_ni = ni - minority_ni

        cash = s("balance_sheet", "cash_minor")
        ar = s("balance_sheet", "accounts_receivable_minor") - ico_trade
        inv = s("balance_sheet", "inventory_minor")
        ppe = s("balance_sheet", "net_ppe_minor")
        total_assets = cash + ar + inv + ppe
        ap = s("balance_sheet", "accounts_payable_minor") - ico_trade
        dtl = s("balance_sheet", "deferred_tax_liability_minor")
        term = s("balance_sheet", "term_debt_minor")
        rev = s("balance_sheet", "revolver_minor")
        total_equity = (
            s("balance_sheet", "common_stock_minor")
            + s("balance_sheet", "additional_paid_in_capital_minor")
            + s("balance_sheet", "retained_earnings_minor")
        )
        controlling_equity = total_equity - minority_equity
        total_le = ap + dtl + term + rev + controlling_equity + minority_equity

        cfads = s("coverage", "cfads_minor")
        debt_service = s("coverage", "debt_service_minor")
        dscr_bps = floordiv(cfads * 10_000, debt_service) if debt_service > 0 else 0
        dscr_breach = debt_service > 0 and dscr_bps < group["min_dscr_bps"]
        ending_total_debt = term + rev
        if idx == 0:
            trailing_ebitda = ebitda
        else:
            trailing_ebitda = floordiv(ebitda + consolidated[idx - 1]["income_statement"]["ebitda_minor"], 2)
        leverage_bps = (
            floordiv(ending_total_debt * 10_000, trailing_ebitda)
            if trailing_ebitda > 0
            else 0
        )
        leverage_breach = trailing_ebitda > 0 and leverage_bps > group["max_leverage_bps"]

        crow = {
            "year": year,
            "income_statement": {
                "revenue_minor": revenue,
                "cogs_minor": cogs,
                "gross_profit_minor": gross,
                "opex_minor": opex,
                "ebitda_minor": ebitda,
                "depreciation_minor": dep,
                "stock_comp_minor": stock_comp,
                "ebit_minor": ebit,
                "interest_expense_minor": interest,
                "pretax_income_minor": pretax,
                "current_tax_expense_minor": current_tax,
                "deferred_tax_expense_minor": deferred_tax,
                "tax_expense_minor": tax_expense,
                "net_income_minor": ni,
                "controlling_net_income_minor": controlling_ni,
                "minority_interest_net_income_minor": minority_ni,
            },
            "eliminations": {
                "intercompany_revenue_minor": ico_rev,
                "intercompany_trade_balance_minor": ico_trade,
            },
            "balance_sheet": {
                "cash_minor": cash,
                "accounts_receivable_minor": ar,
                "inventory_minor": inv,
                "net_ppe_minor": ppe,
                "total_assets_minor": total_assets,
                "accounts_payable_minor": ap,
                "deferred_tax_liability_minor": dtl,
                "term_debt_minor": term,
                "revolver_minor": rev,
                "controlling_equity_minor": controlling_equity,
                "minority_interest_minor": minority_equity,
                "total_liabilities_and_equity_minor": total_le,
            },
            "coverage": {
                "cfads_minor": cfads,
                "debt_service_minor": debt_service,
                "dscr_bps": dscr_bps,
                "dscr_breach": dscr_breach,
                "ending_total_debt_minor": ending_total_debt,
                "trailing_ebitda_minor": trailing_ebitda,
                "leverage_bps": leverage_bps,
                "leverage_breach": leverage_breach,
            },
            "checks": {
                "consolidation_check_minor": total_assets - total_le,
                "net_income_split_check_minor": controlling_ni + minority_ni - ni,
            },
        }
        consolidated.append(crow)

    final = {
        "all_entities_balance": True,
        "consolidation_balances_all_years": True,
        "circular_converged_all_years": True,
        "max_abs_entity_balance_sheet_check_minor": 0,
        "max_abs_entity_cash_reconciliation_check_minor": 0,
        "max_abs_entity_retained_earnings_check_minor": 0,
        "max_abs_entity_ppe_rollforward_check_minor": 0,
        "max_abs_entity_debt_rollforward_check_minor": 0,
        "max_abs_entity_dtl_rollforward_check_minor": 0,
        "max_abs_entity_apic_rollforward_check_minor": 0,
        "max_abs_consolidation_check_minor": 0,
        "max_abs_net_income_split_check_minor": 0,
        "any_dscr_breach": False,
        "any_leverage_breach": False,
    }
    check_map = {
        "balance_sheet_check_minor": "max_abs_entity_balance_sheet_check_minor",
        "cash_reconciliation_check_minor": "max_abs_entity_cash_reconciliation_check_minor",
        "retained_earnings_check_minor": "max_abs_entity_retained_earnings_check_minor",
        "ppe_rollforward_check_minor": "max_abs_entity_ppe_rollforward_check_minor",
        "debt_rollforward_check_minor": "max_abs_entity_debt_rollforward_check_minor",
        "dtl_rollforward_check_minor": "max_abs_entity_dtl_rollforward_check_minor",
        "apic_rollforward_check_minor": "max_abs_entity_apic_rollforward_check_minor",
    }
    for e in entity_out:
        for row in e["years"]:
            for k, v in row["checks"].items():
                final[check_map[k]] = max(final[check_map[k]], abs(v))
            if any(v != 0 for v in row["checks"].values()):
                final["all_entities_balance"] = False
            if not row["debt_schedule"]["circular_converged"]:
                final["circular_converged_all_years"] = False
            if row["coverage"]["dscr_breach"]:
                final["any_dscr_breach"] = True
            if row["coverage"]["leverage_breach"]:
                final["any_leverage_breach"] = True
    for crow in consolidated:
        final["max_abs_consolidation_check_minor"] = max(
            final["max_abs_consolidation_check_minor"],
            abs(crow["checks"]["consolidation_check_minor"]),
        )
        final["max_abs_net_income_split_check_minor"] = max(
            final["max_abs_net_income_split_check_minor"],
            abs(crow["checks"]["net_income_split_check_minor"]),
        )
        if (
            crow["checks"]["consolidation_check_minor"] != 0
            or crow["checks"]["net_income_split_check_minor"] != 0
        ):
            final["consolidation_balances_all_years"] = False
        if crow["coverage"]["dscr_breach"]:
            final["any_dscr_breach"] = True
        if crow["coverage"]["leverage_breach"]:
            final["any_leverage_breach"] = True

    return {"entities": entity_out, "consolidated": consolidated, "final_checks": final}


# --------------------------------------------------------------------------- #
# Assertions and fixtures.
# --------------------------------------------------------------------------- #
def assert_clean_tie_outs(result):
    final = result["final_checks"]
    assert final["all_entities_balance"] is True
    assert final["consolidation_balances_all_years"] is True
    assert final["circular_converged_all_years"] is True
    for key, value in final.items():
        if key.startswith("max_abs_"):
            assert value == 0, f"{key} is {value}"
    for e in result["entities"]:
        for row in e["years"]:
            assert all(v == 0 for v in row["checks"].values()), row
    for crow in result["consolidated"]:
        assert all(v == 0 for v in crow["checks"].values()), crow


def assert_matches_reference(binary, pack):
    actual = run_model(binary, pack)
    expected = reference(copy.deepcopy(pack))
    assert actual == expected, (
        "model output differs from reference\n"
        f"pack={json.dumps(pack, sort_keys=True)}\n"
        f"actual={json.dumps(actual, sort_keys=True)}\n"
        f"expected={json.dumps(expected, sort_keys=True)}"
    )
    assert_clean_tie_outs(actual)


def rebalance_opening(op):
    op["retained_earnings_minor"] = (
        op["cash_minor"]
        + op["accounts_receivable_minor"]
        + op["inventory_minor"]
        + op["net_ppe_minor"]
        - op["accounts_payable_minor"]
        - op["deferred_tax_liability_minor"]
        - op["term_debt_minor"]
        - op["revolver_minor"]
        - op["common_stock_minor"]
        - op["additional_paid_in_capital_minor"]
    )


def entity_assumptions(scale=1.0):
    def arr(vals):
        return list(vals)

    return {
        "revenue_growth_bps": arr([750, 650, 500, 450, 400]),
        "cogs_pct_revenue_bps": arr([5850, 5800, 5750, 5700, 5650]),
        "opex_pct_revenue_bps": arr([2050, 2025, 2000, 1975, 1950]),
        "depreciation_pct_beginning_ppe_bps": arr([1250, 1250, 1250, 1250, 1250]),
        "tax_depreciation_pct_beginning_ppe_bps": arr([2000, 1800, 1600, 1400, 1200]),
        "stock_comp_pct_revenue_bps": arr([200, 190, 180, 170, 160]),
        "capex_pct_revenue_bps": arr([650, 625, 600, 575, 550]),
        "ar_days": arr([45, 44, 43, 42, 41]),
        "inventory_days": arr([55, 54, 52, 50, 48]),
        "ap_days": arr([48, 47, 46, 45, 44]),
        "minimum_cash_pct_revenue_bps": arr([300, 300, 300, 300, 300]),
        "dividend_payout_bps": arr([1500, 1500, 1500, 1500, 1500]),
        "mandatory_amortization_bps": arr([800, 800, 800, 800, 800]),
        "cash_sweep_bps": arr([10000, 10000, 10000, 10000, 10000]),
        "term_spread_bps": arr([200, 175, 150, 125, 100]),
        "revolver_spread_bps": arr([325, 300, 275, 250, 225]),
    }


def base_opening(scale):
    op = {
        "cash_minor": 8_000_000 * scale,
        "accounts_receivable_minor": 15_000_000 * scale,
        "inventory_minor": 9_000_000 * scale,
        "net_ppe_minor": 50_000_000 * scale,
        "accounts_payable_minor": 11_000_000 * scale,
        "deferred_tax_liability_minor": 2_000_000 * scale,
        "term_debt_minor": 30_000_000 * scale,
        "revolver_minor": 5_000_000 * scale,
        "common_stock_minor": 25_000_000 * scale,
        "additional_paid_in_capital_minor": 4_000_000 * scale,
        "retained_earnings_minor": 0,
    }
    rebalance_opening(op)
    return op


def base_pack():
    return {
        "periods": [2027, 2028, 2029, 2030, 2031],
        "group": {
            "tax_rate_bps": [2500, 2500, 2500, 2500, 2500],
            "benchmark_rate_bps": [525, 500, 475, 450, 425],
            "min_dscr_bps": 12500,
            "max_leverage_bps": 60000,
            "max_iterations": 100,
            "convergence_tolerance_minor": 0,
        },
        "entities": [
            {
                "id": "parent",
                "kind": "parent",
                "ownership_bps": 10000,
                "base_revenue_minor": 120_000_000,
                "opening": base_opening(1),
                "assumptions": entity_assumptions(),
            },
            {
                "id": "sub_a",
                "kind": "subsidiary",
                "ownership_bps": 8000,
                "base_revenue_minor": 72_000_000,
                "opening": base_opening(1),
                "assumptions": entity_assumptions(),
            },
            {
                "id": "sub_b",
                "kind": "subsidiary",
                "ownership_bps": 6000,
                "base_revenue_minor": 48_000_000,
                "opening": base_opening(1),
                "assumptions": entity_assumptions(),
            },
        ],
        "intercompany": {
            "revenue_minor": [4_000_000, 4_200_000, 4_400_000, 4_600_000, 4_800_000],
            "trade_balance_minor": [900_000, 950_000, 1_000_000, 1_050_000, 1_100_000],
        },
    }


ENTITY_CHECK_KEYS = {
    "balance_sheet_check_minor",
    "cash_reconciliation_check_minor",
    "retained_earnings_check_minor",
    "ppe_rollforward_check_minor",
    "debt_rollforward_check_minor",
    "dtl_rollforward_check_minor",
    "apic_rollforward_check_minor",
}


def test_reference_model_ties_out():
    result = reference(base_pack())
    assert_clean_tie_outs(result)
    # Circular interest must actually iterate for at least one entity-year.
    assert any(
        row["debt_schedule"]["interest_iterations"] > 1
        for e in result["entities"]
        for row in e["years"]
    )
    # The base case has non-trivial minority interest.
    assert any(
        c["income_statement"]["minority_interest_net_income_minor"] != 0
        for c in result["consolidated"]
    )


def test_output_contract(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert set(out) == {"entities", "consolidated", "final_checks"}
    assert [e["id"] for e in out["entities"]] == ["parent", "sub_a", "sub_b"]
    assert len(out["consolidated"]) == len(pack["periods"])
    first = out["entities"][0]["years"][0]
    assert set(first) == {
        "year",
        "income_statement",
        "tax_schedule",
        "working_capital",
        "cash_flow",
        "debt_schedule",
        "coverage",
        "balance_sheet",
        "checks",
    }
    assert set(first["checks"]) == ENTITY_CHECK_KEYS
    cfirst = out["consolidated"][0]
    assert set(cfirst) == {
        "year",
        "income_statement",
        "eliminations",
        "balance_sheet",
        "coverage",
        "checks",
    }
    assert_matches_reference(binary, pack)


def test_per_entity_rate_joins_group_benchmark_and_entity_spread(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_in, e_out in zip(pack["entities"], out["entities"]):
        a = e_in["assumptions"]
        for idx, row in enumerate(e_out["years"]):
            ds = row["debt_schedule"]
            assert ds["term_rate_bps"] == (
                pack["group"]["benchmark_rate_bps"][idx] + a["term_spread_bps"][idx]
            )
            assert ds["revolver_rate_bps"] == (
                pack["group"]["benchmark_rate_bps"][idx] + a["revolver_spread_bps"][idx]
            )
            # The rate must not be the entity spread alone (a stripped join).
            assert ds["term_rate_bps"] != a["term_spread_bps"][idx]


def test_circular_interest_uses_average_ending_debt(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    parent_y0 = out["entities"][0]["years"][0]
    a = pack["entities"][0]["assumptions"]
    g = pack["group"]
    term_rate = g["benchmark_rate_bps"][0] + a["term_spread_bps"][0]
    rev_rate = g["benchmark_rate_bps"][0] + a["revolver_spread_bps"][0]
    beg_only = bps(pack["entities"][0]["opening"]["term_debt_minor"], term_rate) + bps(
        pack["entities"][0]["opening"]["revolver_minor"], rev_rate
    )
    assert parent_y0["debt_schedule"]["interest_iterations"] > 1
    assert parent_y0["income_statement"]["interest_expense_minor"] != beg_only


def test_intercompany_eliminations_hit_both_sides(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for idx, crow in enumerate(out["consolidated"]):
        ico_rev = pack["intercompany"]["revenue_minor"][idx]
        ico_trade = pack["intercompany"]["trade_balance_minor"][idx]
        gross_revenue = sum(
            e["years"][idx]["income_statement"]["revenue_minor"] for e in out["entities"]
        )
        gross_cogs = sum(
            e["years"][idx]["income_statement"]["cogs_minor"] for e in out["entities"]
        )
        gross_ar = sum(
            e["years"][idx]["balance_sheet"]["accounts_receivable_minor"]
            for e in out["entities"]
        )
        gross_ap = sum(
            e["years"][idx]["balance_sheet"]["accounts_payable_minor"]
            for e in out["entities"]
        )
        # Revenue elimination hits revenue AND cogs equally (gross profit intact).
        assert crow["income_statement"]["revenue_minor"] == gross_revenue - ico_rev
        assert crow["income_statement"]["cogs_minor"] == gross_cogs - ico_rev
        # Trade elimination hits AR AND AP equally (balance sheet stays balanced).
        assert crow["balance_sheet"]["accounts_receivable_minor"] == gross_ar - ico_trade
        assert crow["balance_sheet"]["accounts_payable_minor"] == gross_ap - ico_trade
        assert crow["checks"]["consolidation_check_minor"] == 0


def test_minority_interest_uses_each_subsidiary_ownership(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for idx, crow in enumerate(out["consolidated"]):
        expected_mi = 0
        for e_in, e_out in zip(pack["entities"], out["entities"]):
            own = e_in["ownership_bps"]
            ni = e_out["years"][idx]["income_statement"]["net_income_minor"]
            expected_mi += floordiv((10_000 - own) * ni, 10_000)
        inc = crow["income_statement"]
        assert inc["minority_interest_net_income_minor"] == expected_mi
        assert (
            inc["controlling_net_income_minor"] + inc["minority_interest_net_income_minor"]
            == inc["net_income_minor"]
        )
        # Parent (100% owned) contributes nothing to minority interest.
        assert crow["checks"]["net_income_split_check_minor"] == 0
    # Minority interest is genuinely nonzero somewhere.
    assert any(
        c["income_statement"]["minority_interest_net_income_minor"] != 0
        for c in out["consolidated"]
    )


def test_trailing_leverage_covenant_uses_two_year_average(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_out in out["entities"]:
        for idx, row in enumerate(e_out["years"]):
            ebitda = row["income_statement"]["ebitda_minor"]
            cov = row["coverage"]
            if idx == 0:
                assert cov["trailing_ebitda_minor"] == ebitda
            else:
                prev_ebitda = e_out["years"][idx - 1]["income_statement"]["ebitda_minor"]
                assert cov["trailing_ebitda_minor"] == floordiv(ebitda + prev_ebitda, 2)
            if cov["trailing_ebitda_minor"] > 0:
                assert cov["leverage_bps"] == floordiv(
                    cov["ending_total_debt_minor"] * 10_000,
                    cov["trailing_ebitda_minor"],
                )


def test_dscr_uses_full_debt_service(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_out in out["entities"]:
        for row in e_out["years"]:
            cov = row["coverage"]
            ds = row["debt_schedule"]
            inc = row["income_statement"]
            expected_service = (
                ds["mandatory_amortization_minor"] + inc["interest_expense_minor"]
            )
            assert cov["debt_service_minor"] == expected_service
            expected_cfads = (
                inc["ebitda_minor"]
                - inc["current_tax_expense_minor"]
                - row["cash_flow"]["capex_minor"]
            )
            assert cov["cfads_minor"] == expected_cfads
            if expected_service > 0:
                assert cov["dscr_bps"] == floordiv(
                    cov["cfads_minor"] * 10_000, expected_service
                )


def test_covenant_breach_flags_when_leverage_is_tight(binary):
    pack = base_pack()
    pack["group"]["max_leverage_bps"] = 100  # 1% -> essentially always breached
    out = run_model(binary, pack)
    assert out == reference(pack)
    assert out["final_checks"]["any_leverage_breach"] is True
    assert any(
        row["coverage"]["leverage_breach"]
        for e in out["entities"]
        for row in e["years"]
    )


def test_no_tax_or_dividend_when_pretax_income_is_negative(binary):
    pack = base_pack()
    for e in pack["entities"]:
        e["assumptions"]["cogs_pct_revenue_bps"] = [8800] * len(pack["periods"])
        e["assumptions"]["opex_pct_revenue_bps"] = [2600] * len(pack["periods"])
    out = run_model(binary, pack)
    assert out == reference(pack)
    y0 = out["entities"][0]["years"][0]
    assert y0["income_statement"]["pretax_income_minor"] < 0
    assert y0["income_statement"]["tax_expense_minor"] == 0
    assert y0["income_statement"]["current_tax_expense_minor"] == 0
    assert y0["income_statement"]["deferred_tax_expense_minor"] == 0
    assert y0["cash_flow"]["dividends_minor"] == 0


def test_deferred_taxes_split_book_and_cash_tax(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_in, e_out in zip(pack["entities"], out["entities"]):
        prior_dtl = e_in["opening"]["deferred_tax_liability_minor"]
        for idx, row in enumerate(e_out["years"]):
            inc = row["income_statement"]
            ts = row["tax_schedule"]
            assert (
                inc["current_tax_expense_minor"] + inc["deferred_tax_expense_minor"]
                == inc["tax_expense_minor"]
            )
            expected_book_tax = (
                bps(inc["pretax_income_minor"], pack["group"]["tax_rate_bps"][idx])
                if inc["pretax_income_minor"] > 0
                else 0
            )
            assert inc["tax_expense_minor"] == expected_book_tax
            assert ts["beginning_dtl_minor"] == prior_dtl
            assert ts["ending_dtl_minor"] == prior_dtl + inc["deferred_tax_expense_minor"]
            assert (
                row["balance_sheet"]["deferred_tax_liability_minor"]
                == ts["ending_dtl_minor"]
            )
            assert row["cash_flow"]["deferred_tax_minor"] == inc["deferred_tax_expense_minor"]
            prior_dtl = ts["ending_dtl_minor"]


def test_working_capital_signs_drive_cfo(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_out in out["entities"]:
        for row in e_out["years"]:
            cf = row["cash_flow"]
            expected_cfo = (
                cf["net_income_minor"]
                + cf["depreciation_minor"]
                + cf["stock_comp_minor"]
                + cf["deferred_tax_minor"]
                - cf["change_ar_minor"]
                - cf["change_inventory_minor"]
                + cf["change_ap_minor"]
            )
            assert cf["cfo_minor"] == expected_cfo


def test_stock_comp_is_noncash_and_credits_paid_in_capital(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for e_in, e_out in zip(pack["entities"], out["entities"]):
        prior_apic = e_in["opening"]["additional_paid_in_capital_minor"]
        for row in e_out["years"]:
            inc = row["income_statement"]
            bs = row["balance_sheet"]
            sbc = inc["stock_comp_minor"]
            assert sbc > 0
            assert inc["ebit_minor"] == inc["ebitda_minor"] - inc["depreciation_minor"] - sbc
            assert row["cash_flow"]["stock_comp_minor"] == sbc
            assert bs["additional_paid_in_capital_minor"] == prior_apic + sbc
            assert bs["common_stock_minor"] == e_in["opening"]["common_stock_minor"]
            prior_apic = bs["additional_paid_in_capital_minor"]


def test_consolidated_balance_sheet_ties_out(binary):
    pack = base_pack()
    out = run_model(binary, pack)
    assert out == reference(pack)
    for crow in out["consolidated"]:
        bs = crow["balance_sheet"]
        assert (
            bs["total_assets_minor"]
            == bs["cash_minor"]
            + bs["accounts_receivable_minor"]
            + bs["inventory_minor"]
            + bs["net_ppe_minor"]
        )
        assert (
            bs["total_liabilities_and_equity_minor"]
            == bs["accounts_payable_minor"]
            + bs["deferred_tax_liability_minor"]
            + bs["term_debt_minor"]
            + bs["revolver_minor"]
            + bs["controlling_equity_minor"]
            + bs["minority_interest_minor"]
        )
        assert bs["total_assets_minor"] == bs["total_liabilities_and_equity_minor"]


def test_revolver_draw_protects_minimum_cash(binary):
    pack = base_pack()
    for e in pack["entities"]:
        e["opening"]["cash_minor"] = 500_000
        e["opening"]["term_debt_minor"] = 18_000_000
        e["opening"]["revolver_minor"] = 0
        rebalance_opening(e["opening"])
        e["assumptions"]["capex_pct_revenue_bps"][0] = 3000
    out = run_model(binary, pack)
    assert out == reference(pack)
    y0 = out["entities"][0]["years"][0]
    assert y0["debt_schedule"]["revolver_draw_minor"] > 0
    assert y0["balance_sheet"]["cash_minor"] == bps(
        y0["income_statement"]["revenue_minor"],
        pack["entities"][0]["assumptions"]["minimum_cash_pct_revenue_bps"][0],
    )


def test_excess_cash_repays_revolver_before_term_sweep(binary):
    pack = base_pack()
    for e in pack["entities"]:
        e["opening"]["cash_minor"] = 30_000_000
        e["opening"]["revolver_minor"] = 9_000_000
        rebalance_opening(e["opening"])
    out = run_model(binary, pack)
    assert out == reference(pack)
    y0 = out["entities"][0]["years"][0]
    assert y0["debt_schedule"]["revolver_repayment_minor"] == 9_000_000
    assert y0["debt_schedule"]["cash_sweep_minor"] > 0


def test_mandatory_amortization_is_capped_at_beginning_debt(binary):
    pack = base_pack()
    for e in pack["entities"]:
        e["opening"]["term_debt_minor"] = 500_000
        e["opening"]["revolver_minor"] = 0
        e["assumptions"]["mandatory_amortization_bps"] = [20_000] * len(pack["periods"])
        rebalance_opening(e["opening"])
    out = run_model(binary, pack)
    assert out == reference(pack)
    y0 = out["entities"][0]["years"][0]["debt_schedule"]
    assert y0["mandatory_amortization_minor"] == 500_000
    assert y0["ending_term_debt_minor"] == 0


def build_random_pack(rng):
    n = rng.randint(3, 6)
    years = list(range(2027, 2027 + n))

    def choices(vals):
        return [rng.choice(vals) for _ in years]

    def rand_entity(eid, kind, own):
        base_revenue = rng.randint(40_000_000, 300_000_000)
        cash = rng.randint(500_000, 25_000_000)
        ar = days(base_revenue, rng.randint(25, 70))
        cogs_seed = bps(base_revenue, rng.randint(4200, 7600))
        inv = days(cogs_seed, rng.randint(20, 95))
        ppe = rng.randint(15_000_000, 160_000_000)
        ap = days(cogs_seed, rng.randint(20, 75))
        term = rng.randint(0, 120_000_000)
        rev = rng.randint(0, 25_000_000)
        common = rng.randint(5_000_000, 60_000_000)
        apic = rng.randint(0, 30_000_000)
        dtl = rng.randint(0, 8_000_000)
        op = {
            "cash_minor": cash,
            "accounts_receivable_minor": ar,
            "inventory_minor": inv,
            "net_ppe_minor": ppe,
            "accounts_payable_minor": ap,
            "deferred_tax_liability_minor": dtl,
            "term_debt_minor": term,
            "revolver_minor": rev,
            "common_stock_minor": common,
            "additional_paid_in_capital_minor": apic,
            "retained_earnings_minor": 0,
        }
        rebalance_opening(op)
        book_dep_bps = choices([500, 900, 1250, 1600, 2200])
        tax_dep_bps = [b + rng.choice([0, 300, 700, 1200, 2500]) for b in book_dep_bps]
        return {
            "id": eid,
            "kind": kind,
            "ownership_bps": own,
            "base_revenue_minor": base_revenue,
            "opening": op,
            "assumptions": {
                "revenue_growth_bps": choices([-500, 0, 250, 500, 800, 1200, 1800]),
                "cogs_pct_revenue_bps": choices([4500, 5200, 5800, 6400, 7200, 8500]),
                "opex_pct_revenue_bps": choices([1200, 1800, 2300, 3000, 4200]),
                "depreciation_pct_beginning_ppe_bps": book_dep_bps,
                "tax_depreciation_pct_beginning_ppe_bps": tax_dep_bps,
                "stock_comp_pct_revenue_bps": choices([0, 100, 250, 400]),
                "capex_pct_revenue_bps": choices([200, 500, 800, 1400, 2500]),
                "ar_days": choices([30, 40, 50, 65, 80]),
                "inventory_days": choices([20, 35, 55, 75, 100]),
                "ap_days": choices([20, 35, 50, 70, 90]),
                "minimum_cash_pct_revenue_bps": choices([100, 250, 400, 750]),
                "dividend_payout_bps": choices([0, 0, 1000, 2500]),
                "mandatory_amortization_bps": choices([0, 300, 800, 1500]),
                "cash_sweep_bps": choices([5000, 7500, 10000]),
                "term_spread_bps": choices([100, 200, 350, 500]),
                "revolver_spread_bps": choices([200, 350, 550, 750]),
            },
        }

    entities = [
        rand_entity("parent", "parent", 10000),
        rand_entity("sub_a", "subsidiary", rng.choice([5100, 6000, 7500, 8000, 9000])),
        rand_entity("sub_b", "subsidiary", rng.choice([5100, 6500, 7000, 8500, 9500])),
    ]
    return {
        "periods": years,
        "group": {
            "tax_rate_bps": choices([0, 2100, 2500, 2800]),
            "benchmark_rate_bps": choices([300, 425, 525, 650]),
            "min_dscr_bps": rng.choice([10000, 12500, 15000]),
            "max_leverage_bps": rng.choice([30000, 45000, 60000, 90000]),
            "max_iterations": 100,
            # A one-minor-unit tolerance absorbs integer floor jitter in the
            # average-debt solve; the solver must read it from the pack.
            "convergence_tolerance_minor": 1,
        },
        "entities": entities,
        "intercompany": {
            "revenue_minor": [rng.randint(0, 6_000_000) for _ in years],
            "trade_balance_minor": [rng.randint(0, 1_500_000) for _ in years],
        },
    }


def test_randomized_consolidated_model_cases(binary):
    rng = random.Random(20260707)
    for _ in range(150):
        pack = build_random_pack(rng)
        assert_matches_reference(binary, pack)
