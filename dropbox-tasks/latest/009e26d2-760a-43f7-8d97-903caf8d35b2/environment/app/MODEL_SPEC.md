# Consolidated multi-entity three-statement model specification

This is the accounting reference for the projection engine in `main.go`. The
engine reads a **manifest** that points at three sibling documents, projects the
three statements for each legal entity in the group, computes coverage
covenants, and then consolidates the group with intercompany eliminations and a
controlling / non-controlling interest split. Every per-entity statement and the
consolidated statements must tie out to the penny.

## Documents and how they join

The program reads one manifest JSON path from `os.Args[1]` and prints one JSON
object to stdout. Keep that command-line interface and the existing JSON keys
unchanged. The manifest references three sibling files, resolved **relative to
the manifest's own directory**:

```
manifest.json      { "periods": [year...], "documents": { "group", "entities", "intercompany" } }
group.json         group-wide, per-period macro assumptions (arrays indexed by period)
entities.json      { "entities": [ { id, kind, ownership_bps, base_revenue_minor, opening{}, assumptions{} } ] }
intercompany.json  { "revenue_minor": [per period], "trade_balance_minor": [per period] }
```

The three documents must be joined on two keys: the **entity id** (each entity
is projected from its own opening balance sheet and its own assumptions) and the
**period index** (position `i` in `periods`; every per-period array —- in the
group doc, each entity's assumptions, and the intercompany doc —- is indexed by
that same `i`). A value from one entity or one period must never be applied to
another. `group.json` supplies what is common to the whole group in a period
(the statutory tax rate, the benchmark interest rate, covenant thresholds, and
the circular-solve controls); `entities.json` supplies what is specific to each
entity; `intercompany.json` supplies the eliminations for the period.

## Arithmetic conventions

Use integer math throughout. Money is in minor units and ratios are basis points
(`10000` = 100%). The `bps` helper (`amount * ratio / 10000`) and the `days`
helper (`amount * days / 365`) are applied only to non-negative amounts, so
truncation equals floor. Derived **metrics** (DSCR, leverage, minority interest)
can take negative inputs and must use signed **floor** division, not truncation.

Project the periods one at a time from the prior period balance sheet, and
project each entity independently. Revenue grows from the previous revenue; all
other operating figures come from that period's assumption index. AR is based on
revenue days; inventory and AP are based on COGS days. Taxes and dividends are
never negative.

## Per-entity income statement

Revenue, COGS, gross profit, opex, and EBITDA are as usual. Below EBITDA two
non-cash charges precede EBIT:

1. Book depreciation = beginning net PP&E × `depreciation_pct_beginning_ppe_bps`,
   capped at beginning net PP&E.
2. Stock-based compensation = revenue × `stock_comp_pct_revenue_bps`; a non-cash
   operating expense below EBITDA (EBITDA excludes it).

```text
EBIT          = EBITDA - book depreciation - stock-based compensation
pretax income = EBIT - interest expense
```

## Per-entity taxes and deferred taxes

The statutory rate is the group's `tax_rate_bps` for the period (a shared macro
assumption, not an entity assumption).

- Book tax expense = `tax_rate_bps` × pretax income when pretax income is
  positive, else zero. This is the income-statement tax.
- Tax depreciation = beginning net PP&E × `tax_depreciation_pct_beginning_ppe_bps`,
  capped at beginning net PP&E; used only to size taxable income.
- Temporary difference = tax depreciation − book depreciation.
- Taxable income = pretax income − temporary difference.
- Current (cash) tax = `tax_rate_bps` × taxable income when taxable income is
  positive, else zero.
- Deferred tax expense = book tax − current tax (either sign); it is the change
  in the deferred tax liability: `ending DTL = beginning DTL + deferred tax`.
- Net income = pretax income − book tax.

Stock-based compensation is deductible for tax when expensed, so only the
depreciation timing difference creates deferred tax.

## Per-entity working capital and cash flow

```text
CFO = net income
    + book depreciation
    + stock-based compensation
    + deferred tax expense
    - increase in AR
    - increase in inventory
    + increase in AP
```

Only the deferred portion of tax is added back (the current tax is the cash tax
that leaves the business). CFI is `-capex`. Dividends come from positive net
income only (`dividend_payout_bps`).

## Per-entity equity, PP&E, retained earnings

- Net PP&E rolls forward by capex less book depreciation.
- Stock-based compensation credits additional paid-in capital
  (`ending APIC = beginning APIC + SBC`); common stock does not change.
- Retained earnings roll forward by net income less dividends.

## Per-entity debt, interest, and the circular solve

Each entity's interest rates are **derived per period** by adding the entity's
spread to the group benchmark:

```text
term rate     = group benchmark_rate_bps[period] + entity term_spread_bps[period]
revolver rate = group benchmark_rate_bps[period] + entity revolver_spread_bps[period]
```

Interest is circular: it is charged on average term and revolver debt, while
ending debt depends on the cash left after interest. Compute a seed estimate
before the loop by treating ending debt as beginning debt (seed = beginning-debt
interest); the seed is not a counted pass. Then run passes numbered from `1`.
Each pass uses the current estimate to compute the statements and financing
decision, yielding new ending balances and a new estimate from the average-debt
formula. Compare the new estimate to the estimate the pass started from:

- If they differ by no more than `convergence_tolerance_minor`, that pass is the
  final pass: record its number as `interest_iterations`, set `circular_converged`
  to true, and stop. Do not run another pass after convergence is detected.
  Report the interest, debt balances, cash movements, iteration count, and
  convergence flag from that same final pass.
- Otherwise adopt the new estimate and run the next pass, up to `max_iterations`.

Financing runs in order: (1) mandatory term amortization capped at beginning term
debt; (2) cash after CFO, capex, dividends, and mandatory amortization; (3) if
below minimum cash, draw the revolver exactly enough to reach the minimum (no
repayment or sweep in that case); (4) otherwise repay the beginning revolver
first out of the excess above minimum cash; (5) sweep the remaining excess to
term debt at `cash_sweep_bps`, capped at term debt after mandatory amortization.

```text
term interest     = floor((beginning term + ending term) * term rate / 20000)
revolver interest = floor((beginning revolver + ending revolver) * revolver rate / 20000)
interest expense  = term interest + revolver interest
```

## Per-entity coverage covenants

Reported in each entity-year's `coverage` block:

- `cfads = EBITDA - current tax - capex`.
- `debt_service = mandatory amortization + interest expense`.
- `dscr_bps = floordiv(cfads * 10000, debt_service)` when debt_service > 0, else
  `0`. `dscr_breach = debt_service > 0 and dscr_bps < group.min_dscr_bps`.
- `ending_total_debt = ending term + ending revolver`.
- `trailing_ebitda` is a **two-year average**: for the first period it is that
  period's EBITDA; for every later period it is
  `floordiv(EBITDA[period] + EBITDA[period-1], 2)` for the **same entity**.
- `leverage_bps = floordiv(ending_total_debt * 10000, trailing_ebitda)` when
  trailing_ebitda > 0, else `0`.
  `leverage_breach = trailing_ebitda > 0 and leverage_bps > group.max_leverage_bps`.

Breach flags are legitimate data outcomes, not errors; they do not affect the
tie-out checks.

## Consolidation

For each period, the group is consolidated from the per-entity results:

- **Intercompany revenue** `intercompany.revenue_minor[period]` is removed from
  consolidated revenue **and** consolidated COGS equally (so consolidated gross
  profit and EBITDA are unaffected).
- **Intercompany trade balance** `intercompany.trade_balance_minor[period]` is
  removed from consolidated AR **and** consolidated AP equally (so the
  consolidated balance sheet stays balanced).
- Every other income-statement and balance-sheet line is the sum across all
  entities.
- **Minority interest.** For each entity, using that entity's own
  `ownership_bps`:
  `minority NI += floordiv((10000 - ownership_bps) * entity net income, 10000)`
  and `minority equity += floordiv((10000 - ownership_bps) * entity book equity, 10000)`,
  where entity book equity = common + APIC + retained earnings. The parent is
  100%-owned (`ownership_bps = 10000`) and contributes nothing to minority
  interest. `controlling net income = consolidated net income - minority NI` and
  `controlling equity = total book equity - minority equity`.
- Consolidated `coverage` uses summed entity CFADS and debt service, with the
  same DSCR and two-year-trailing leverage formulas applied to consolidated
  EBITDA.

Consolidated checks per period (must be zero):

- `consolidation_check = total assets - total liabilities and equity`, where
  total L&E = AP + DTL + term + revolver + controlling equity + minority interest.
- `net_income_split_check = controlling NI + minority NI - consolidated NI`.

## Output and final checks

The output is `{ "entities": [...], "consolidated": [...], "final_checks": {...} }`.
Each entity object has `id`, `kind`, `ownership_bps`, and `years` (per-period rows
with income statement, tax schedule, working capital, cash flow, debt schedule,
coverage, balance sheet, and the seven per-entity checks). Each consolidated year
has income statement (including controlling and minority net income),
eliminations, balance sheet, coverage, and checks.

`final_checks` reports `all_entities_balance`, `consolidation_balances_all_years`,
and `circular_converged_all_years` (all must be true when the model is correct),
the `max_abs_*` of every entity and consolidated check (all zero when correct),
and the informational `any_dscr_breach` / `any_leverage_breach` flags.
