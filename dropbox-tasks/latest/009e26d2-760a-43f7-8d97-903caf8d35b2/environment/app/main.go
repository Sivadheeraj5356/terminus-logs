package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type manifest struct {
	Periods   []int `json:"periods"`
	Documents struct {
		Group        string `json:"group"`
		Entities     string `json:"entities"`
		Intercompany string `json:"intercompany"`
	} `json:"documents"`
}

type group struct {
	TaxRateBps                []int64 `json:"tax_rate_bps"`
	BenchmarkRateBps          []int64 `json:"benchmark_rate_bps"`
	MinDSCRBps                int64   `json:"min_dscr_bps"`
	MaxLeverageBps            int64   `json:"max_leverage_bps"`
	MaxIterations             int     `json:"max_iterations"`
	ConvergenceToleranceMinor int64   `json:"convergence_tolerance_minor"`
}

type opening struct {
	CashMinor                    int64 `json:"cash_minor"`
	AccountsReceivableMinor      int64 `json:"accounts_receivable_minor"`
	InventoryMinor               int64 `json:"inventory_minor"`
	NetPPEMinor                  int64 `json:"net_ppe_minor"`
	AccountsPayableMinor         int64 `json:"accounts_payable_minor"`
	DeferredTaxLiabilityMinor    int64 `json:"deferred_tax_liability_minor"`
	TermDebtMinor                int64 `json:"term_debt_minor"`
	RevolverMinor                int64 `json:"revolver_minor"`
	CommonStockMinor             int64 `json:"common_stock_minor"`
	AdditionalPaidInCapitalMinor int64 `json:"additional_paid_in_capital_minor"`
	RetainedEarningsMinor        int64 `json:"retained_earnings_minor"`
}

type assumptions struct {
	RevenueGrowthBps                  []int64 `json:"revenue_growth_bps"`
	COGSPctRevenueBps                 []int64 `json:"cogs_pct_revenue_bps"`
	OpexPctRevenueBps                 []int64 `json:"opex_pct_revenue_bps"`
	DepreciationPctBeginningPPEBps    []int64 `json:"depreciation_pct_beginning_ppe_bps"`
	TaxDepreciationPctBeginningPPEBps []int64 `json:"tax_depreciation_pct_beginning_ppe_bps"`
	StockCompPctRevenueBps            []int64 `json:"stock_comp_pct_revenue_bps"`
	CapexPctRevenueBps                []int64 `json:"capex_pct_revenue_bps"`
	ARDays                            []int64 `json:"ar_days"`
	InventoryDays                     []int64 `json:"inventory_days"`
	APDays                            []int64 `json:"ap_days"`
	MinimumCashPctRevenueBps          []int64 `json:"minimum_cash_pct_revenue_bps"`
	DividendPayoutBps                 []int64 `json:"dividend_payout_bps"`
	MandatoryAmortizationBps          []int64 `json:"mandatory_amortization_bps"`
	CashSweepBps                      []int64 `json:"cash_sweep_bps"`
	TermSpreadBps                     []int64 `json:"term_spread_bps"`
	RevolverSpreadBps                 []int64 `json:"revolver_spread_bps"`
}

type entity struct {
	ID               string      `json:"id"`
	Kind             string      `json:"kind"`
	OwnershipBps     int64       `json:"ownership_bps"`
	BaseRevenueMinor int64       `json:"base_revenue_minor"`
	Opening          opening     `json:"opening"`
	Assumptions      assumptions `json:"assumptions"`
}

type entitiesDoc struct {
	Entities []entity `json:"entities"`
}

type intercompany struct {
	RevenueMinor      []int64 `json:"revenue_minor"`
	TradeBalanceMinor []int64 `json:"trade_balance_minor"`
}

type incomeStatement struct {
	RevenueMinor            int64 `json:"revenue_minor"`
	COGSMinor               int64 `json:"cogs_minor"`
	GrossProfitMinor        int64 `json:"gross_profit_minor"`
	OpexMinor               int64 `json:"opex_minor"`
	EBITDAMinor             int64 `json:"ebitda_minor"`
	DepreciationMinor       int64 `json:"depreciation_minor"`
	StockCompMinor          int64 `json:"stock_comp_minor"`
	EBITMinor               int64 `json:"ebit_minor"`
	InterestExpenseMinor    int64 `json:"interest_expense_minor"`
	PretaxIncomeMinor       int64 `json:"pretax_income_minor"`
	CurrentTaxExpenseMinor  int64 `json:"current_tax_expense_minor"`
	DeferredTaxExpenseMinor int64 `json:"deferred_tax_expense_minor"`
	TaxExpenseMinor         int64 `json:"tax_expense_minor"`
	NetIncomeMinor          int64 `json:"net_income_minor"`
}

type consIncomeStatement struct {
	incomeStatement
	ControllingNetIncomeMinor      int64 `json:"controlling_net_income_minor"`
	MinorityInterestNetIncomeMinor int64 `json:"minority_interest_net_income_minor"`
}

type taxSchedule struct {
	TaxDepreciationMinor     int64 `json:"tax_depreciation_minor"`
	TemporaryDifferenceMinor int64 `json:"temporary_difference_minor"`
	TaxableIncomeMinor       int64 `json:"taxable_income_minor"`
	BeginningDTLMinor        int64 `json:"beginning_dtl_minor"`
	DeferredTaxExpenseMinor  int64 `json:"deferred_tax_expense_minor"`
	EndingDTLMinor           int64 `json:"ending_dtl_minor"`
}

type workingCapital struct {
	AccountsReceivableMinor int64 `json:"accounts_receivable_minor"`
	InventoryMinor          int64 `json:"inventory_minor"`
	AccountsPayableMinor    int64 `json:"accounts_payable_minor"`
	ChangeARMinor           int64 `json:"change_ar_minor"`
	ChangeInventoryMinor    int64 `json:"change_inventory_minor"`
	ChangeAPMinor           int64 `json:"change_ap_minor"`
}

type cashFlow struct {
	NetIncomeMinor       int64 `json:"net_income_minor"`
	DepreciationMinor    int64 `json:"depreciation_minor"`
	StockCompMinor       int64 `json:"stock_comp_minor"`
	DeferredTaxMinor     int64 `json:"deferred_tax_minor"`
	ChangeARMinor        int64 `json:"change_ar_minor"`
	ChangeInventoryMinor int64 `json:"change_inventory_minor"`
	ChangeAPMinor        int64 `json:"change_ap_minor"`
	CFOMinor             int64 `json:"cfo_minor"`
	CapexMinor           int64 `json:"capex_minor"`
	CFIMinor             int64 `json:"cfi_minor"`
	DividendsMinor       int64 `json:"dividends_minor"`
	CFFMinor             int64 `json:"cff_minor"`
	NetChangeCashMinor   int64 `json:"net_change_cash_minor"`
	EndingCashMinor      int64 `json:"ending_cash_minor"`
}

type debtSchedule struct {
	BeginningTermDebtMinor     int64 `json:"beginning_term_debt_minor"`
	BeginningRevolverMinor     int64 `json:"beginning_revolver_minor"`
	TermRateBps                int64 `json:"term_rate_bps"`
	RevolverRateBps            int64 `json:"revolver_rate_bps"`
	MandatoryAmortizationMinor int64 `json:"mandatory_amortization_minor"`
	CashSweepMinor             int64 `json:"cash_sweep_minor"`
	RevolverDrawMinor          int64 `json:"revolver_draw_minor"`
	RevolverRepaymentMinor     int64 `json:"revolver_repayment_minor"`
	EndingTermDebtMinor        int64 `json:"ending_term_debt_minor"`
	EndingRevolverMinor        int64 `json:"ending_revolver_minor"`
	InterestExpenseMinor       int64 `json:"interest_expense_minor"`
	InterestIterations         int   `json:"interest_iterations"`
	CircularConverged          bool  `json:"circular_converged"`
}

type coverage struct {
	CFADSMinor           int64 `json:"cfads_minor"`
	DebtServiceMinor     int64 `json:"debt_service_minor"`
	DSCRBps              int64 `json:"dscr_bps"`
	DSCRBreach           bool  `json:"dscr_breach"`
	EndingTotalDebtMinor int64 `json:"ending_total_debt_minor"`
	TrailingEBITDAMinor  int64 `json:"trailing_ebitda_minor"`
	LeverageBps          int64 `json:"leverage_bps"`
	LeverageBreach       bool  `json:"leverage_breach"`
}

type balanceSheet struct {
	CashMinor                      int64 `json:"cash_minor"`
	AccountsReceivableMinor        int64 `json:"accounts_receivable_minor"`
	InventoryMinor                 int64 `json:"inventory_minor"`
	NetPPEMinor                    int64 `json:"net_ppe_minor"`
	TotalAssetsMinor               int64 `json:"total_assets_minor"`
	AccountsPayableMinor           int64 `json:"accounts_payable_minor"`
	DeferredTaxLiabilityMinor      int64 `json:"deferred_tax_liability_minor"`
	TermDebtMinor                  int64 `json:"term_debt_minor"`
	RevolverMinor                  int64 `json:"revolver_minor"`
	CommonStockMinor               int64 `json:"common_stock_minor"`
	AdditionalPaidInCapitalMinor   int64 `json:"additional_paid_in_capital_minor"`
	RetainedEarningsMinor          int64 `json:"retained_earnings_minor"`
	TotalLiabilitiesAndEquityMinor int64 `json:"total_liabilities_and_equity_minor"`
}

type checks struct {
	BalanceSheetCheckMinor       int64 `json:"balance_sheet_check_minor"`
	CashReconciliationCheckMinor int64 `json:"cash_reconciliation_check_minor"`
	RetainedEarningsCheckMinor   int64 `json:"retained_earnings_check_minor"`
	PPERollforwardCheckMinor     int64 `json:"ppe_rollforward_check_minor"`
	DebtRollforwardCheckMinor    int64 `json:"debt_rollforward_check_minor"`
	DTLRollforwardCheckMinor     int64 `json:"dtl_rollforward_check_minor"`
	APICRollforwardCheckMinor    int64 `json:"apic_rollforward_check_minor"`
}

type yearOutput struct {
	Year            int             `json:"year"`
	IncomeStatement incomeStatement `json:"income_statement"`
	TaxSchedule     taxSchedule     `json:"tax_schedule"`
	WorkingCapital  workingCapital  `json:"working_capital"`
	CashFlow        cashFlow        `json:"cash_flow"`
	DebtSchedule    debtSchedule    `json:"debt_schedule"`
	Coverage        coverage        `json:"coverage"`
	BalanceSheet    balanceSheet    `json:"balance_sheet"`
	Checks          checks          `json:"checks"`
}

type entityOutput struct {
	ID           string       `json:"id"`
	Kind         string       `json:"kind"`
	OwnershipBps int64        `json:"ownership_bps"`
	Years        []yearOutput `json:"years"`
}

type eliminations struct {
	IntercompanyRevenueMinor      int64 `json:"intercompany_revenue_minor"`
	IntercompanyTradeBalanceMinor int64 `json:"intercompany_trade_balance_minor"`
}

type consBalanceSheet struct {
	CashMinor                      int64 `json:"cash_minor"`
	AccountsReceivableMinor        int64 `json:"accounts_receivable_minor"`
	InventoryMinor                 int64 `json:"inventory_minor"`
	NetPPEMinor                    int64 `json:"net_ppe_minor"`
	TotalAssetsMinor               int64 `json:"total_assets_minor"`
	AccountsPayableMinor           int64 `json:"accounts_payable_minor"`
	DeferredTaxLiabilityMinor      int64 `json:"deferred_tax_liability_minor"`
	TermDebtMinor                  int64 `json:"term_debt_minor"`
	RevolverMinor                  int64 `json:"revolver_minor"`
	ControllingEquityMinor         int64 `json:"controlling_equity_minor"`
	MinorityInterestMinor          int64 `json:"minority_interest_minor"`
	TotalLiabilitiesAndEquityMinor int64 `json:"total_liabilities_and_equity_minor"`
}

type consChecks struct {
	ConsolidationCheckMinor  int64 `json:"consolidation_check_minor"`
	NetIncomeSplitCheckMinor int64 `json:"net_income_split_check_minor"`
}

type consYear struct {
	Year            int                 `json:"year"`
	IncomeStatement consIncomeStatement `json:"income_statement"`
	Eliminations    eliminations        `json:"eliminations"`
	BalanceSheet    consBalanceSheet    `json:"balance_sheet"`
	Coverage        coverage            `json:"coverage"`
	Checks          consChecks          `json:"checks"`
}

type finalChecks struct {
	AllEntitiesBalance                    bool  `json:"all_entities_balance"`
	ConsolidationBalancesAllYears         bool  `json:"consolidation_balances_all_years"`
	CircularConvergedAllYears             bool  `json:"circular_converged_all_years"`
	MaxAbsEntityBalanceSheetCheckMinor    int64 `json:"max_abs_entity_balance_sheet_check_minor"`
	MaxAbsEntityCashReconciliationMinor   int64 `json:"max_abs_entity_cash_reconciliation_check_minor"`
	MaxAbsEntityRetainedEarningsMinor     int64 `json:"max_abs_entity_retained_earnings_check_minor"`
	MaxAbsEntityPPERollforwardMinor       int64 `json:"max_abs_entity_ppe_rollforward_check_minor"`
	MaxAbsEntityDebtRollforwardMinor      int64 `json:"max_abs_entity_debt_rollforward_check_minor"`
	MaxAbsEntityDTLRollforwardMinor       int64 `json:"max_abs_entity_dtl_rollforward_check_minor"`
	MaxAbsEntityAPICRollforwardMinor      int64 `json:"max_abs_entity_apic_rollforward_check_minor"`
	MaxAbsConsolidationCheckMinor         int64 `json:"max_abs_consolidation_check_minor"`
	MaxAbsNetIncomeSplitCheckMinor        int64 `json:"max_abs_net_income_split_check_minor"`
	AnyDSCRBreach                         bool  `json:"any_dscr_breach"`
	AnyLeverageBreach                     bool  `json:"any_leverage_breach"`
}

type response struct {
	Entities     []entityOutput `json:"entities"`
	Consolidated []consYear     `json:"consolidated"`
	FinalChecks  finalChecks    `json:"final_checks"`
}

type state struct {
	Cash       int64
	AR         int64
	Inv        int64
	PPE        int64
	AP         int64
	TermDebt   int64
	Revolver   int64
	Common     int64
	APIC       int64
	DTL        int64
	Retained   int64
	Revenue    int64
	PrevEBITDA int64
}

type calc struct {
	row          yearOutput
	next         state
	nextInterest int64
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: consolidated_model <manifest.json>")
		os.Exit(2)
	}
	manifestPath := os.Args[1]
	dir := filepath.Dir(manifestPath)

	var m manifest
	mustRead(manifestPath, &m)
	var g group
	mustRead(filepath.Join(dir, m.Documents.Group), &g)
	var ed entitiesDoc
	mustRead(filepath.Join(dir, m.Documents.Entities), &ed)
	var ico intercompany
	mustRead(filepath.Join(dir, m.Documents.Intercompany), &ico)

	out := project(m.Periods, g, ed.Entities, ico)
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, "write output:", err)
		os.Exit(1)
	}
}

func mustRead(path string, v interface{}) {
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read", path, ":", err)
		os.Exit(1)
	}
	if err := json.Unmarshal(data, v); err != nil {
		fmt.Fprintln(os.Stderr, "parse", path, ":", err)
		os.Exit(1)
	}
}

func project(periods []int, g group, entities []entity, ico intercompany) response {
	out := response{}
	out.FinalChecks.AllEntitiesBalance = true
	out.FinalChecks.ConsolidationBalancesAllYears = true
	out.FinalChecks.CircularConvergedAllYears = true

	entityRows := make(map[string][]yearOutput)
	for _, ent := range entities {
		rows := projectEntity(periods, g, ent)
		entityRows[ent.ID] = rows
		out.Entities = append(out.Entities, entityOutput{
			ID: ent.ID, Kind: ent.Kind, OwnershipBps: ent.OwnershipBps, Years: rows,
		})
		for _, row := range rows {
			c := row.Checks
			fc := &out.FinalChecks
			fc.MaxAbsEntityBalanceSheetCheckMinor = max64(fc.MaxAbsEntityBalanceSheetCheckMinor, abs64(c.BalanceSheetCheckMinor))
			fc.MaxAbsEntityCashReconciliationMinor = max64(fc.MaxAbsEntityCashReconciliationMinor, abs64(c.CashReconciliationCheckMinor))
			fc.MaxAbsEntityRetainedEarningsMinor = max64(fc.MaxAbsEntityRetainedEarningsMinor, abs64(c.RetainedEarningsCheckMinor))
			fc.MaxAbsEntityPPERollforwardMinor = max64(fc.MaxAbsEntityPPERollforwardMinor, abs64(c.PPERollforwardCheckMinor))
			fc.MaxAbsEntityDebtRollforwardMinor = max64(fc.MaxAbsEntityDebtRollforwardMinor, abs64(c.DebtRollforwardCheckMinor))
			fc.MaxAbsEntityDTLRollforwardMinor = max64(fc.MaxAbsEntityDTLRollforwardMinor, abs64(c.DTLRollforwardCheckMinor))
			fc.MaxAbsEntityAPICRollforwardMinor = max64(fc.MaxAbsEntityAPICRollforwardMinor, abs64(c.APICRollforwardCheckMinor))
			if c.BalanceSheetCheckMinor != 0 || c.CashReconciliationCheckMinor != 0 ||
				c.RetainedEarningsCheckMinor != 0 || c.PPERollforwardCheckMinor != 0 ||
				c.DebtRollforwardCheckMinor != 0 || c.DTLRollforwardCheckMinor != 0 ||
				c.APICRollforwardCheckMinor != 0 {
				fc.AllEntitiesBalance = false
			}
			if !row.DebtSchedule.CircularConverged {
				fc.CircularConvergedAllYears = false
			}
			if row.Coverage.DSCRBreach {
				fc.AnyDSCRBreach = true
			}
			if row.Coverage.LeverageBreach {
				fc.AnyLeverageBreach = true
			}
		}
	}

	for idx, year := range periods {
		icoRev := ico.RevenueMinor[idx]
		icoTrade := ico.TradeBalanceMinor[idx]

		var revenue, cogs, opex, dep, stockComp, ebit, interest int64
		var pretax, currentTax, deferredTax, taxExpense, ni int64
		var cash, ar, inv, ppe, ap, dtl, term, rev int64
		var totalEquity, minorityNI, minorityEquity int64
		var cfads, debtService int64

		for _, ent := range entities {
			r := entityRows[ent.ID][idx]
			is := r.IncomeStatement
			bs := r.BalanceSheet
			cov := r.Coverage
			revenue += is.RevenueMinor
			cogs += is.COGSMinor
			opex += is.OpexMinor
			dep += is.DepreciationMinor
			stockComp += is.StockCompMinor
			ebit += is.EBITMinor
			interest += is.InterestExpenseMinor
			pretax += is.PretaxIncomeMinor
			currentTax += is.CurrentTaxExpenseMinor
			deferredTax += is.DeferredTaxExpenseMinor
			taxExpense += is.TaxExpenseMinor
			ni += is.NetIncomeMinor
			cash += bs.CashMinor
			ar += bs.AccountsReceivableMinor
			inv += bs.InventoryMinor
			ppe += bs.NetPPEMinor
			ap += bs.AccountsPayableMinor
			dtl += bs.DeferredTaxLiabilityMinor
			term += bs.TermDebtMinor
			rev += bs.RevolverMinor
			eEquity := bs.CommonStockMinor + bs.AdditionalPaidInCapitalMinor + bs.RetainedEarningsMinor
			totalEquity += eEquity
			_ = eEquity
			cfads += cov.CFADSMinor
			debtService += cov.DebtServiceMinor
		}

		revenue -= icoRev
		cogs -= icoRev
		gross := revenue - cogs
		ebitda := gross - opex
		ar -= icoTrade
		totalAssets := cash + ar + inv + ppe
		controllingEquity := totalEquity - minorityEquity
		totalLE := ap + dtl + term + rev + controllingEquity + minorityEquity
		controllingNI := ni - minorityNI

		dscr := int64(0)
		dscrBreach := false
		if debtService > 0 {
			dscr = floorDiv(cfads*10000, debtService)
			dscrBreach = dscr < g.MinDSCRBps
		}
		endingTotalDebt := term + rev
		trailingEBITDA := ebitda
		leverage := int64(0)
		leverageBreach := false
		if trailingEBITDA > 0 {
			leverage = floorDiv(endingTotalDebt*10000, trailingEBITDA)
			leverageBreach = leverage > g.MaxLeverageBps
		}

		crow := consYear{
			Year: year,
			IncomeStatement: consIncomeStatement{
				incomeStatement: incomeStatement{
					RevenueMinor: revenue, COGSMinor: cogs, GrossProfitMinor: gross, OpexMinor: opex,
					EBITDAMinor: ebitda, DepreciationMinor: dep, StockCompMinor: stockComp, EBITMinor: ebit,
					InterestExpenseMinor: interest, PretaxIncomeMinor: pretax,
					CurrentTaxExpenseMinor: currentTax, DeferredTaxExpenseMinor: deferredTax,
					TaxExpenseMinor: taxExpense, NetIncomeMinor: ni,
				},
				ControllingNetIncomeMinor:      controllingNI,
				MinorityInterestNetIncomeMinor: minorityNI,
			},
			Eliminations: eliminations{IntercompanyRevenueMinor: icoRev, IntercompanyTradeBalanceMinor: icoTrade},
			BalanceSheet: consBalanceSheet{
				CashMinor: cash, AccountsReceivableMinor: ar, InventoryMinor: inv, NetPPEMinor: ppe,
				TotalAssetsMinor: totalAssets, AccountsPayableMinor: ap, DeferredTaxLiabilityMinor: dtl,
				TermDebtMinor: term, RevolverMinor: rev, ControllingEquityMinor: controllingEquity,
				MinorityInterestMinor: minorityEquity, TotalLiabilitiesAndEquityMinor: totalLE,
			},
			Coverage: coverage{
				CFADSMinor: cfads, DebtServiceMinor: debtService, DSCRBps: dscr, DSCRBreach: dscrBreach,
				EndingTotalDebtMinor: endingTotalDebt, TrailingEBITDAMinor: trailingEBITDA,
				LeverageBps: leverage, LeverageBreach: leverageBreach,
			},
			Checks: consChecks{
				ConsolidationCheckMinor:  totalAssets - totalLE,
				NetIncomeSplitCheckMinor: controllingNI + minorityNI - ni,
			},
		}
		out.Consolidated = append(out.Consolidated, crow)

		fc := &out.FinalChecks
		fc.MaxAbsConsolidationCheckMinor = max64(fc.MaxAbsConsolidationCheckMinor, abs64(crow.Checks.ConsolidationCheckMinor))
		fc.MaxAbsNetIncomeSplitCheckMinor = max64(fc.MaxAbsNetIncomeSplitCheckMinor, abs64(crow.Checks.NetIncomeSplitCheckMinor))
		if crow.Checks.ConsolidationCheckMinor != 0 || crow.Checks.NetIncomeSplitCheckMinor != 0 {
			fc.ConsolidationBalancesAllYears = false
		}
		if crow.Coverage.DSCRBreach {
			fc.AnyDSCRBreach = true
		}
		if crow.Coverage.LeverageBreach {
			fc.AnyLeverageBreach = true
		}
	}

	return out
}

func projectEntity(periods []int, g group, ent entity) []yearOutput {
	op := ent.Opening
	st := state{
		Cash: op.CashMinor, AR: op.AccountsReceivableMinor, Inv: op.InventoryMinor, PPE: op.NetPPEMinor,
		AP: op.AccountsPayableMinor, TermDebt: op.TermDebtMinor, Revolver: op.RevolverMinor,
		Common: op.CommonStockMinor, APIC: op.AdditionalPaidInCapitalMinor, DTL: op.DeferredTaxLiabilityMinor,
		Retained: op.RetainedEarningsMinor, Revenue: ent.BaseRevenueMinor, PrevEBITDA: 0,
	}
	a := ent.Assumptions
	maxIter := g.MaxIterations
	if maxIter <= 0 {
		maxIter = 100
	}
	tolerance := g.ConvergenceToleranceMinor
	rows := make([]yearOutput, 0, len(periods))
	for i, yr := range periods {
		termRate := a.TermSpreadBps[i]
		revRate := a.RevolverSpreadBps[i]
		guess := interestFromDebt(st.TermDebt, st.TermDebt, termRate, st.Revolver, st.Revolver, revRate)
		converged := false
		iterations := 0
		var c calc
		for iter := 1; iter <= maxIter; iter++ {
			c = calcEntityYear(g, ent, st, i, yr, guess, iter, false)
			iterations = iter
			if abs64(c.nextInterest-guess) <= tolerance {
				converged = true
				break
			}
			guess = c.nextInterest
		}
		c.row.DebtSchedule.InterestIterations = iterations
		c.row.DebtSchedule.CircularConverged = converged
		st = c.next
		rows = append(rows, c.row)
	}
	return rows
}

func calcEntityYear(g group, ent entity, beg state, i int, yr int, interest int64, iterations int, converged bool) calc {
	a := ent.Assumptions
	taxRate := g.TaxRateBps[i]
	termRate := a.TermSpreadBps[i]
	revRate := a.RevolverSpreadBps[i]

	revenue := bps(beg.Revenue, 10000+a.RevenueGrowthBps[i])
	cogs := bps(revenue, a.COGSPctRevenueBps[i])
	gross := revenue - cogs
	opex := bps(revenue, a.OpexPctRevenueBps[i])
	ebitda := gross - opex
	bookDep := min64(beg.PPE, bps(beg.PPE, a.DepreciationPctBeginningPPEBps[i]))
	taxDep := min64(beg.PPE, bps(beg.PPE, a.TaxDepreciationPctBeginningPPEBps[i]))
	stockComp := bps(revenue, a.StockCompPctRevenueBps[i])
	ebit := ebitda - bookDep - stockComp
	pretax := ebit - interest

	bookTax := int64(0)
	if pretax > 0 {
		bookTax = bps(pretax, taxRate)
	}
	tempDiff := taxDep - bookDep
	taxableIncome := pretax - tempDiff
	currentTax := bookTax
	deferredTax := int64(0)
	taxExpense := bookTax
	ni := pretax - taxExpense
	dividends := int64(0)
	if ni > 0 {
		dividends = bps(ni, a.DividendPayoutBps[i])
	}

	endAR := days(revenue, a.ARDays[i])
	endInv := days(cogs, a.InventoryDays[i])
	endAP := days(cogs, a.APDays[i])
	dAR := endAR - beg.AR
	dInv := endInv - beg.Inv
	dAP := endAP - beg.AP
	cfo := ni + bookDep + stockComp + deferredTax - dAR + dInv + dAP
	capex := bps(revenue, a.CapexPctRevenueBps[i])
	cfi := -capex
	mandatory := min64(beg.TermDebt, bps(beg.TermDebt, a.MandatoryAmortizationBps[i]))
	minCash := bps(revenue, a.MinimumCashPctRevenueBps[i])
	cashBeforeFinancing := beg.Cash + cfo - capex - dividends - mandatory

	draw, repay, sweep := int64(0), int64(0), int64(0)
	termAfterMandatory := beg.TermDebt - mandatory
	if cashBeforeFinancing < minCash {
		draw = minCash - cashBeforeFinancing
	} else {
		excess := cashBeforeFinancing - minCash
		repay = min64(beg.Revolver, excess)
		excess -= repay
		sweep = min64(termAfterMandatory, bps(excess, a.CashSweepBps[i]))
	}

	endTerm := termAfterMandatory - sweep
	endRev := beg.Revolver + draw - repay
	nextInterest := interestFromDebt(beg.TermDebt, endTerm, termRate, beg.Revolver, endRev, revRate)
	cff := -dividends - mandatory - sweep + draw - repay
	netChange := cfo + cfi + cff
	endCash := beg.Cash + netChange
	endPPE := beg.PPE + capex - bookDep
	endDTL := beg.DTL + deferredTax
	endAPIC := beg.APIC + stockComp
	endRetained := beg.Retained + ni - dividends

	cfads := ebitda - currentTax - capex
	debtService := interest
	dscr := int64(0)
	dscrBreach := false
	if debtService > 0 {
		dscr = floorDiv(cfads*10000, debtService)
		dscrBreach = dscr < g.MinDSCRBps
	}
	endingTotalDebt := endTerm + endRev
	trailingEBITDA := ebitda
	leverage := int64(0)
	leverageBreach := false
	if trailingEBITDA > 0 {
		leverage = floorDiv(endingTotalDebt*10000, trailingEBITDA)
		leverageBreach = leverage > g.MaxLeverageBps
	}

	bs := balanceSheet{
		CashMinor: endCash, AccountsReceivableMinor: endAR, InventoryMinor: endInv, NetPPEMinor: endPPE,
		AccountsPayableMinor: endAP, DeferredTaxLiabilityMinor: endDTL, TermDebtMinor: endTerm, RevolverMinor: endRev,
		CommonStockMinor: beg.Common, AdditionalPaidInCapitalMinor: endAPIC, RetainedEarningsMinor: endRetained,
	}
	bs.TotalAssetsMinor = bs.CashMinor + bs.AccountsReceivableMinor + bs.InventoryMinor + bs.NetPPEMinor
	bs.TotalLiabilitiesAndEquityMinor = bs.AccountsPayableMinor + bs.DeferredTaxLiabilityMinor + bs.TermDebtMinor + bs.RevolverMinor + bs.CommonStockMinor + bs.AdditionalPaidInCapitalMinor + bs.RetainedEarningsMinor

	row := yearOutput{
		Year: yr,
		IncomeStatement: incomeStatement{
			RevenueMinor: revenue, COGSMinor: cogs, GrossProfitMinor: gross, OpexMinor: opex,
			EBITDAMinor: ebitda, DepreciationMinor: bookDep, StockCompMinor: stockComp, EBITMinor: ebit,
			InterestExpenseMinor: interest, PretaxIncomeMinor: pretax,
			CurrentTaxExpenseMinor: currentTax, DeferredTaxExpenseMinor: deferredTax,
			TaxExpenseMinor: taxExpense, NetIncomeMinor: ni,
		},
		TaxSchedule: taxSchedule{
			TaxDepreciationMinor: taxDep, TemporaryDifferenceMinor: tempDiff, TaxableIncomeMinor: taxableIncome,
			BeginningDTLMinor: beg.DTL, DeferredTaxExpenseMinor: deferredTax, EndingDTLMinor: endDTL,
		},
		WorkingCapital: workingCapital{
			AccountsReceivableMinor: endAR, InventoryMinor: endInv, AccountsPayableMinor: endAP,
			ChangeARMinor: dAR, ChangeInventoryMinor: dInv, ChangeAPMinor: dAP,
		},
		CashFlow: cashFlow{
			NetIncomeMinor: ni, DepreciationMinor: bookDep, StockCompMinor: stockComp, DeferredTaxMinor: deferredTax,
			ChangeARMinor: dAR, ChangeInventoryMinor: dInv, ChangeAPMinor: dAP, CFOMinor: cfo,
			CapexMinor: capex, CFIMinor: cfi, DividendsMinor: dividends,
			CFFMinor: cff, NetChangeCashMinor: netChange, EndingCashMinor: endCash,
		},
		DebtSchedule: debtSchedule{
			BeginningTermDebtMinor: beg.TermDebt, BeginningRevolverMinor: beg.Revolver,
			TermRateBps: termRate, RevolverRateBps: revRate,
			MandatoryAmortizationMinor: mandatory, CashSweepMinor: sweep, RevolverDrawMinor: draw,
			RevolverRepaymentMinor: repay, EndingTermDebtMinor: endTerm, EndingRevolverMinor: endRev,
			InterestExpenseMinor: interest, InterestIterations: iterations, CircularConverged: converged,
		},
		Coverage: coverage{
			CFADSMinor: cfads, DebtServiceMinor: debtService, DSCRBps: dscr, DSCRBreach: dscrBreach,
			EndingTotalDebtMinor: endingTotalDebt, TrailingEBITDAMinor: trailingEBITDA,
			LeverageBps: leverage, LeverageBreach: leverageBreach,
		},
		BalanceSheet: bs,
	}
	row.Checks = checks{
		BalanceSheetCheckMinor:       bs.TotalAssetsMinor - bs.TotalLiabilitiesAndEquityMinor,
		CashReconciliationCheckMinor: beg.Cash + netChange - endCash,
		RetainedEarningsCheckMinor:   beg.Retained + ni - dividends - endRetained,
		PPERollforwardCheckMinor:     beg.PPE + capex - bookDep - endPPE,
		DebtRollforwardCheckMinor:    beg.TermDebt + beg.Revolver + draw - repay - mandatory - sweep - endTerm - endRev,
		DTLRollforwardCheckMinor:     beg.DTL + deferredTax - endDTL,
		APICRollforwardCheckMinor:    beg.APIC + stockComp - endAPIC,
	}
	next := state{Cash: endCash, AR: endAR, Inv: endInv, PPE: endPPE, AP: endAP, TermDebt: endTerm,
		Revolver: endRev, Common: beg.Common, APIC: endAPIC, DTL: endDTL, Retained: endRetained,
		Revenue: revenue, PrevEBITDA: ebitda}
	return calc{row: row, next: next, nextInterest: nextInterest}
}

func interestFromDebt(begTerm, endTerm, termRate, begRev, endRev, revRate int64) int64 {
	return (begTerm+endTerm)*termRate/20000 + (begRev+endRev)*revRate/20000
}

func bps(amount int64, r int64) int64 {
	return amount * r / 10000
}

func days(amount int64, d int64) int64 {
	return amount * d / 365
}

func floorDiv(a, b int64) int64 {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

func min64(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}

func max64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func abs64(v int64) int64 {
	if v < 0 {
		return -v
	}
	return v
}
