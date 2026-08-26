package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

type LineItem struct {
	Service           string `json:"service"`
	Units             int64  `json:"units"`
	ListCost          int64  `json:"list_cost_microcents"`
	CommittedUnits    int64  `json:"committed_units"`
	CommittedDiscount int64  `json:"committed_discount_microcents"`
	OnDemandUnits     int64  `json:"on_demand_units"`
	OnDemandCost      int64  `json:"on_demand_cost_microcents"`
}

type TenantLedger struct {
	TenantID           string     `json:"tenant_id"`
	Name               string     `json:"name"`
	LineItems          []LineItem `json:"line_items"`
	Subtotal           int64      `json:"subtotal_microcents"`
	CreditApplied      int64      `json:"credit_applied_microcents"`
	CommitmentDiscount int64      `json:"commitment_discount_microcents"`
	NetUsage           int64      `json:"net_usage_microcents"`
	SharedAllocated    int64      `json:"shared_allocated_microcents"`
	TotalCharge        int64      `json:"total_charge_microcents"`
}

type Summary struct {
	TenantCount        int   `json:"tenant_count"`
	TotalBillable      int64 `json:"total_billable_microcents"`
	PoolTotal          int64 `json:"pool_total_microcents"`
	PoolUnallocated    int64 `json:"pool_unallocated_microcents"`
	CreditApplied      int64 `json:"credit_applied_microcents"`
	CommitmentDiscount int64 `json:"commitment_discount_microcents"`
}

type Ledger struct {
	PeriodID     string         `json:"period_id"`
	Currency     string         `json:"currency"`
	Tenants      []TenantLedger `json:"tenants"`
	Summary      Summary        `json:"summary"`
	ReportDigest string         `json:"report_digest"`
}

func sortLedger(rows []TenantLedger) {
	sort.SliceStable(rows, func(i, j int) bool {
		if rows[i].TotalCharge != rows[j].TotalCharge {
			return rows[i].TotalCharge > rows[j].TotalCharge
		}
		return rows[i].TenantID < rows[j].TenantID
	})
}

func writeLedger(outDir string, l Ledger) {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		panic(err)
	}
	b, err := json.MarshalIndent(l, "", "  ")
	if err != nil {
		panic(err)
	}
	b = append(b, '\n')
	if err := os.WriteFile(filepath.Join(outDir, "ledger.json"), b, 0o644); err != nil {
		panic(err)
	}
}
