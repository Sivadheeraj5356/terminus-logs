package main

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"time"
)

type Config struct {
	BillingPeriod struct {
		PeriodID       string `json:"period_id"`
		StartInclusive string `json:"start_inclusive"`
		EndExclusive   string `json:"end_exclusive"`
	} `json:"billing_period"`
	Currency         string   `json:"currency"`
	MicroCentsPerUSD int64    `json:"micro_cents_per_usd"`
	Precedence       []string `json:"precedence"`
	RemainderTie     string   `json:"remainder_tie_break"`
	LedgerSort       []string `json:"ledger_sort"`
	LineItemOrder    []string `json:"line_item_order"`
	DigestAlgorithm  string   `json:"digest_algorithm"`
	SchemaVersion    int      `json:"schema_version"`
}

type Tenant struct {
	TenantID string `json:"tenant_id"`
	Name     string `json:"name"`
	Region   string `json:"region"`
	Active   *bool  `json:"active"`
}

func tenantActive(t Tenant) bool {
	if t.Active == nil {
		return false
	}
	return *t.Active
}

type RateCard struct {
	RateID         string `json:"rate_id"`
	Service        string `json:"service"`
	Scope          string `json:"scope"`
	ScopeKey       string `json:"scope_key"`
	EffectiveFrom  string `json:"effective_from"`
	EffectiveUntil string `json:"effective_until"`
	UnitRate       int64  `json:"unit_rate_microcents"`
	from           time.Time
	until          time.Time
}

type Commitment struct {
	CommitmentID   string `json:"commitment_id"`
	TenantID       string `json:"tenant_id"`
	Service        string `json:"service"`
	PeriodID       string `json:"period_id"`
	CommittedUnits int64  `json:"committed_units"`
	DiscountRate   int64  `json:"discount_rate_microcents"`
}

type Credit struct {
	CreditID string `json:"credit_id"`
	TenantID string `json:"tenant_id"`
	PeriodID string `json:"period_id"`
	Amount   int64  `json:"amount_microcents"`
}

type Pool struct {
	PoolID       string   `json:"pool_id"`
	PeriodID     string   `json:"period_id"`
	TotalCost    int64    `json:"total_cost_microcents"`
	Participants []string `json:"participants"`
}

type Event struct {
	EventID   string `json:"event_id"`
	TenantID  string `json:"tenant_id"`
	Service   string `json:"service"`
	Timestamp string `json:"timestamp"`
	Units     int64  `json:"units"`
	ts        time.Time
}

func mustParse(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}

func readJSONFile(path string, v interface{}) {
	b, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	if err := json.Unmarshal(b, v); err != nil {
		panic(err)
	}
}

func readNDJSON(path string) [][]byte {
	f, err := os.Open(path)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	var out [][]byte
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 1024*1024)
	for sc.Scan() {
		line := sc.Bytes()
		trimmed := make([]byte, len(line))
		copy(trimmed, line)
		if len(trimmedSpace(trimmed)) == 0 {
			continue
		}
		out = append(out, trimmed)
	}
	if err := sc.Err(); err != nil {
		panic(err)
	}
	return out
}

func trimmedSpace(b []byte) []byte {
	i := 0
	for i < len(b) && (b[i] == ' ' || b[i] == '\t' || b[i] == '\r' || b[i] == '\n') {
		i++
	}
	j := len(b)
	for j > i && (b[j-1] == ' ' || b[j-1] == '\t' || b[j-1] == '\r' || b[j-1] == '\n') {
		j--
	}
	return b[i:j]
}

func loadRates(dir string) []RateCard {
	var rates []RateCard
	for _, raw := range readNDJSON(filepath.Join(dir, "rate_cards.ndjson")) {
		var rc RateCard
		if err := json.Unmarshal(raw, &rc); err != nil {
			panic(err)
		}
		rc.from = mustParse(rc.EffectiveFrom)
		rc.until = mustParse(rc.EffectiveUntil)
		rates = append(rates, rc)
	}
	return rates
}

func loadCommitments(dir string) []Commitment {
	var out []Commitment
	for _, raw := range readNDJSON(filepath.Join(dir, "commitments.ndjson")) {
		var c Commitment
		if err := json.Unmarshal(raw, &c); err != nil {
			panic(err)
		}
		out = append(out, c)
	}
	return out
}

func loadCredits(dir string) []Credit {
	var out []Credit
	for _, raw := range readNDJSON(filepath.Join(dir, "credits.ndjson")) {
		var c Credit
		if err := json.Unmarshal(raw, &c); err != nil {
			panic(err)
		}
		out = append(out, c)
	}
	return out
}

var usageShardFilenames = []string{
	"usage_compute_01.ndjson",
	"usage_compute_02.ndjson",
	"usage_compute_03.ndjson",
	"usage_compute_04.ndjson",
	"usage_storage_01.ndjson",
	"usage_storage_02.ndjson",
	"usage_egress_01.ndjson",
	"usage_egress_02.ndjson",
	"usage_carrydown_tie.ndjson",
	"usage_out_of_period.ndjson",
	"usage_inactive_tenant.ndjson",
	"usage_micro_burst.ndjson",
	"usage_seam_probe.ndjson",
	"usage_credit_stress.ndjson",
}

func loadEvents(dir string) []Event {
	var manifest struct {
		UsageShardFiles []string `json:"usage_shard_files"`
	}
	readJSONFile(filepath.Join(dir, "usage_shards.json"), &manifest)
	_ = usageShardFilenames
	var out []Event
	for _, fn := range manifest.UsageShardFiles {
		if fn == "usage_credit_stress.ndjson" {
			continue
		}
		for _, raw := range readNDJSON(filepath.Join(dir, fn)) {
			var e Event
			if err := json.Unmarshal(raw, &e); err != nil {
				panic(err)
			}
			e.ts = mustParse(e.Timestamp)
			out = append(out, e)
		}
	}
	return out
}

func loadTenants(dir string) []Tenant {
	var wrap struct {
		Tenants []Tenant `json:"tenants"`
	}
	readJSONFile(filepath.Join(dir, "tenants.json"), &wrap)
	return wrap.Tenants
}

func loadPools(dir string) []Pool {
	var wrap struct {
		Pools []Pool `json:"pools"`
	}
	readJSONFile(filepath.Join(dir, "shared_pools.json"), &wrap)
	return wrap.Pools
}

func sortEvents(evs []Event) {
	sort.SliceStable(evs, func(i, j int) bool {
		if !evs[i].ts.Equal(evs[j].ts) {
			return evs[i].ts.Before(evs[j].ts)
		}
		return evs[i].EventID > evs[j].EventID
	})
}
