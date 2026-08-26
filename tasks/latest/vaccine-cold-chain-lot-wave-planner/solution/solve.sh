#!/bin/bash
set -euo pipefail

cd /app/environment

cat > lotledger/pick.go <<'GO'
package lotledger

import (
	"encoding/json"
	"os"
	"sort"

	"immunoflow/pkg/api"
)

const remainderPath = "/app/var/immunoflow_vialremainder.json"

type RemainderState map[string]int

type Pool struct {
	left map[string]int
	meta map[string]api.Lot
}

func loadRemainder() RemainderState {
	raw, err := os.ReadFile(remainderPath)
	if err != nil {
		return RemainderState{}
	}
	s := RemainderState{}
	_ = json.Unmarshal(raw, &s)
	return s
}

func saveRemainder(s RemainderState) error {
	raw, _ := json.MarshalIndent(s, "", "  ")
	return os.WriteFile(remainderPath, append(raw, '\n'), 0o644)
}

func NewPool(lots []api.Lot) *Pool {
	st := loadRemainder()
	p := &Pool{left: map[string]int{}, meta: map[string]api.Lot{}}
	for _, lot := range lots {
		avail := lot.Doses
		if rem, ok := st[lot.LotID]; ok {
			avail = lot.Doses - rem
		}
		if avail < 0 {
			avail = 0
		}
		p.left[lot.LotID] = avail
		p.meta[lot.LotID] = lot
	}
	return p
}

func op_a(lots []api.Lot) []api.Lot {
	out := append([]api.Lot(nil), lots...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].ExpiryDay == out[j].ExpiryDay {
			return out[i].LotID < out[j].LotID
		}
		return out[i].ExpiryDay < out[j].ExpiryDay
	})
	return out
}

func PickLots(lots []api.Lot, need int, vial int) ([]api.LotAssignment, error) {
	p := NewPool(lots)
	if len(lots) == 0 {
		return nil, nil
	}
	return p.Draw(lots[0].TempBand, need, vial)
}

func (p *Pool) Draw(temp string, need int, vial int) ([]api.LotAssignment, error) {
	candidates := []api.Lot{}
	for id, left := range p.left {
		if left <= 0 {
			continue
		}
		lot := p.meta[id]
		if lot.TempBand != temp {
			continue
		}
		row := lot
		row.Doses = left
		candidates = append(candidates, row)
	}
	st := loadRemainder()
	remain := need
	out := []api.LotAssignment{}
	for _, lot := range op_a(candidates) {
		if remain <= 0 {
			break
		}
		avail := p.left[lot.LotID]
		if avail <= 0 {
			continue
		}
		give := avail
		if give > remain {
			give = remain
		}
		remain -= give
		p.left[lot.LotID] = avail - give
		st[lot.LotID] = (st[lot.LotID] + give) % vial
		out = append(out, api.LotAssignment{LotID: lot.LotID, Doses: give, TempBand: lot.TempBand})
	}
	if err := saveRemainder(st); err != nil {
		return nil, err
	}
	return out, nil
}
GO

cat > wavebook/gap.go <<'GO'
package wavebook

func GapWeeks(minGapDays int) int {
	return (minGapDays + 6) / 7
}

func phase_b(dose1Wave int, minGapDays int) int {
	return dose1Wave + GapWeeks(minGapDays)
}

func Dose2Wave(dose1Wave int, minGapDays int) int {
	return phase_b(dose1Wave, minGapDays)
}
GO

cat > equitygate/floor.go <<'GO'
package equitygate

import "immunoflow/pkg/api"

type EquityRollup struct {
	RegionDelivered map[string]int `json:"region_delivered"`
	EquityMet       bool           `json:"equity_met"`
}

func reconcile_c(regions []api.Region, delivered map[string]int, reserve int) EquityRollup {
	_ = reserve
	out := EquityRollup{RegionDelivered: map[string]int{}, EquityMet: true}
	for _, r := range regions {
		got := delivered[r.RegionID]
		out.RegionDelivered[r.RegionID] = got
		if got < r.EquityFloor {
			out.EquityMet = false
		}
	}
	return out
}

func Reconcile(regions []api.Region, delivered map[string]int, reserve int) EquityRollup {
	return reconcile_c(regions, delivered, reserve)
}
GO

cat > coldlane/bind.go <<'GO'
package coldlane

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"

	"immunoflow/pkg/api"
)

type packReq struct {
	Assignments []api.LotAssignment `json:"assignments"`
}

type packResp struct {
	Pallets map[string][]string `json:"pallets"`
}

func grp_q(assign []api.LotAssignment) map[string][]string {
	out := map[string][]string{}
	band := map[string]string{}
	for _, r := range assign {
		key := r.PalletID
		if prev, ok := band[key]; ok && prev != r.TempBand {
			key = r.PalletID + "-" + r.TempBand
		}
		band[key] = r.TempBand
		out[key] = append(out[key], r.LotID)
	}
	return out
}

func Bind(assign []api.LotAssignment) map[string][]string {
	dir, err := os.MkdirTemp("", "pkmerge-*")
	if err != nil {
		return grp_q(assign)
	}
	defer os.RemoveAll(dir)
	inPath := filepath.Join(dir, "in.json")
	outPath := filepath.Join(dir, "out.json")
	body, err := json.Marshal(packReq{Assignments: assign})
	if err != nil {
		return grp_q(assign)
	}
	if err := os.WriteFile(inPath, body, 0o644); err != nil {
		return grp_q(assign)
	}
	cmd := exec.Command("/app/bin/pkmerge", "--in", inPath, "--out", outPath)
	if err := cmd.Run(); err != nil {
		return grp_q(assign)
	}
	raw, err := os.ReadFile(outPath)
	if err != nil {
		return grp_q(assign)
	}
	var resp packResp
	if err := json.Unmarshal(raw, &resp); err != nil || resp.Pallets == nil {
		return grp_q(assign)
	}
	return resp.Pallets
}
GO


cat > staging/plan_cache.go <<'GO'
package staging

import (
	"encoding/json"
	"os"

	"immunoflow/pkg/api"
)

const cachePath = "/app/var/immunoflow_plan_cache.json"

type CacheDoc struct {
	Generation int                `json:"generation"`
	Wave       int                `json:"wave"`
	Plan       api.AllocationPlan `json:"plan"`
}

func Store(doc CacheDoc) error {
	raw, _ := json.MarshalIndent(doc, "", "  ")
	return os.WriteFile(cachePath, append(raw, '\n'), 0o644)
}

func recall_b(generation int) (CacheDoc, error) {
	raw, err := os.ReadFile(cachePath)
	if err != nil {
		return CacheDoc{}, err
	}
	var d CacheDoc
	if err := json.Unmarshal(raw, &d); err != nil {
		return CacheDoc{}, err
	}
	if d.Generation != generation {
		return CacheDoc{Plan: api.AllocationPlan{LotAssignments: []api.LotAssignment{}}}, nil
	}
	return d, nil
}

func Recall(generation int) (CacheDoc, error) {
	return recall_b(generation)
}
GO

cat > scopebook/ledger.go <<'GO'
package scopebook

import (
	"encoding/json"
	"os"
)

const ledgerPath = "/app/var/immunoflow_scopebook.json"

type Ledger struct {
	Generation     int `json:"generation"`
	TotalLaneHours int `json:"total_lane_hours"`
}

func Load() Ledger {
	raw, err := os.ReadFile(ledgerPath)
	if err != nil {
		return Ledger{}
	}
	var l Ledger
	_ = json.Unmarshal(raw, &l)
	return l
}

func Save(l Ledger) error {
	raw, _ := json.MarshalIndent(l, "", "  ")
	return os.WriteFile(ledgerPath, append(raw, '\n'), 0o644)
}

func record_d(next int) error {
	l := Load()
	l.Generation += 1
	l.TotalLaneHours += next
	return Save(l)
}

func Record(next int) error {
	return record_d(next)
}
GO

cat > emit/plan.go <<'GO'
package emit

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"immunoflow/coldlane"
	"immunoflow/equitygate"
	"immunoflow/internal/ingest"
	"immunoflow/lotledger"
	"immunoflow/pkg/api"
	"immunoflow/scopebook"
	"immunoflow/staging"
	"immunoflow/support"
	"immunoflow/wavebook"
)

const cfgPath = "/app/config/immuno.toml"

func writeJSON(path string, v any) error {
	raw, _ := json.MarshalIndent(v, "", "  ")
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

func digestPlan(plan api.AllocationPlan) string {
	parts := []string{}
	for _, a := range plan.LotAssignments {
		parts = append(parts, fmt.Sprintf("%s:%s:%d", a.RegionID, a.LotID, a.Doses))
	}
	sort.Strings(parts)
	h := sha256.Sum256([]byte(fmt.Sprintf("%d|%s", plan.Wave, strings.Join(parts, "|"))))
	return hex.EncodeToString(h[:])
}

func BenchReset() error {
	_ = os.MkdirAll("/app/var", 0o755)
	_ = writeJSON("/app/var/immunoflow_vialremainder.json", map[string]int{})
	_ = writeJSON("/app/var/immunoflow_customs.json", map[string]any{"total_delay_days": 0, "by_region": map[string]int{}})
	_ = writeJSON("/app/var/immunoflow_scopebook.json", map[string]int{"generation": 0, "total_lane_hours": 0})
	return writeJSON("/app/var/immunoflow_plan_cache.json", map[string]any{"generation": 0, "wave": 0, "plan": map[string]any{}})
}

func assemble_x(lab string, wave int) (api.AllocationPlan, ingest.Bundle, error) {
	b, err := ingest.LoadAll(lab, cfgPath)
	if err != nil {
		return api.AllocationPlan{}, b, err
	}
	routes := map[string]api.Route{}
	hours := 0
	for _, r := range b.Routes {
		routes[r.RegionID] = r
		hours += r.LaneHours
	}
	_ = scopebook.Record(hours)
	regions := append([]api.Region(nil), b.Regions...)
	sort.Slice(regions, func(i, j int) bool { return regions[i].RegionID < regions[j].RegionID })
	pool := lotledger.NewPool(b.Lots)
	delivered := map[string]int{}
	assign := []api.LotAssignment{}
	for _, region := range regions {
		picked, err := pool.Draw(region.StorageTemp, region.DemandDose1, b.Config.VialSize)
		if err != nil {
			return api.AllocationPlan{}, b, err
		}
		for _, p := range picked {
			route := routes[region.RegionID]
			row := p
			row.RegionID = region.RegionID
			row.PalletID = route.PalletID
			assign = append(assign, row)
			delivered[region.RegionID] += row.Doses
		}
	}
	eq := equitygate.Reconcile(b.Regions, delivered, b.Config.ReserveDoses)
	cov := []api.RegionCoverage{}
	for _, r := range regions {
		d := delivered[r.RegionID]
		ratio := 0.0
		if r.DemandDose1 > 0 {
			ratio = float64(d) / float64(r.DemandDose1)
		}
		cov = append(cov, api.RegionCoverage{RegionID: r.RegionID, Delivered: d, Need: r.DemandDose1, CoverageRatio: ratio})
	}
	plan := api.AllocationPlan{Wave: wave, LotAssignments: assign, RegionCoverage: cov, EquityMet: eq.EquityMet}
	plan.PlanDigestHex = digestPlan(plan)
	return plan, b, nil
}

func writeCSV(path string, plan api.AllocationPlan, routes []api.Route) error {
	idx := map[string]api.Route{}
	for _, r := range routes {
		idx[r.RegionID] = r
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	_ = w.Write([]string{"leg_id", "region_id", "lot_id", "depart_day", "arrive_day", "temp_band"})
	for _, row := range plan.LotAssignments {
		leg := idx[row.RegionID]
		_ = w.Write([]string{leg.LegID, row.RegionID, row.LotID, fmt.Sprint(leg.DepartDay), fmt.Sprint(leg.ArriveDay), row.TempBand})
	}
	w.Flush()
	return w.Error()
}

func PlanWave(lab string, wave int, out string) error {
	_ = os.MkdirAll("/app/output", 0o755)
	plan, b, err := assemble_x(lab, wave)
	if err != nil {
		return err
	}
	if err := writeJSON(out, plan); err != nil {
		return err
	}
	_ = writeCSV("/app/output/shipment_legs.csv", plan, b.Routes)
	served := map[string]bool{}
	for _, row := range plan.LotAssignments {
		served[row.RegionID] = true
	}
	c := support.LoadCustoms()
	for _, r := range b.Routes {
		if !served[r.RegionID] {
			continue
		}
		c.TotalDelayDays += r.CustomsDelayDays
		c.ByRegion[r.RegionID] += r.CustomsDelayDays
	}
	_ = support.SaveCustoms(c)
	_ = staging.Store(staging.CacheDoc{Generation: scopebook.Load().Generation, Wave: wave, Plan: plan})
	delivered := map[string]int{}
	for _, row := range plan.RegionCoverage {
		delivered[row.RegionID] = row.Delivered
	}
	rollup := equitygate.Reconcile(b.Regions, delivered, b.Config.ReserveDoses)
	_ = writeJSON("/app/output/equity_rollup.json", rollup)
	_ = writeJSON("/app/output/feasibility_report.json", map[string]any{"wave": wave, "feasible": plan.EquityMet})
	return nil
}

func BindLanes(wave int, planPath, out string) error {
	raw, err := os.ReadFile(planPath)
	if err != nil {
		return err
	}
	var plan api.AllocationPlan
	if err := json.Unmarshal(raw, &plan); err != nil {
		return err
	}
	pallets := coldlane.Bind(plan.LotAssignments)
	sum := sha256.Sum256([]byte(fmt.Sprintf("%v", pallets)))
	return writeJSON(out, map[string]any{"wave": wave, "pallets": pallets, "spoilage_rows": []map[string]any{}, "lane_digest_hex": hex.EncodeToString(sum[:])})
}

func ScheduleDoses(lab string, dose1 int) error {
	b, err := ingest.LoadAll(lab, cfgPath)
	if err != nil {
		return err
	}
	rows := []map[string]any{}
	for _, c := range b.Clinics {
		rows = append(rows, map[string]any{
			"clinic_id":    c.ClinicID,
			"dose1_wave":   dose1,
			"dose2_wave":   wavebook.Dose2Wave(dose1, c.MinGapDays),
			"min_gap_days": c.MinGapDays,
		})
	}
	return writeJSON("/app/output/dose_schedule.json", map[string]any{"schedule": rows})
}

func ReconcileEquity(lab, planPath string) error {
	b, err := ingest.LoadAll(lab, cfgPath)
	if err != nil {
		return err
	}
	raw, err := os.ReadFile(planPath)
	if err != nil {
		return err
	}
	var plan api.AllocationPlan
	if err := json.Unmarshal(raw, &plan); err != nil {
		return err
	}
	d := map[string]int{}
	for _, r := range plan.RegionCoverage {
		d[r.RegionID] = r.Delivered
	}
	return writeJSON("/app/output/equity_rollup.json", equitygate.Reconcile(b.Regions, d, b.Config.ReserveDoses))
}

func ProjectInfections(lab, planPath string) error {
	b, err := ingest.LoadAll(lab, cfgPath)
	if err != nil {
		return err
	}
	raw, err := os.ReadFile(planPath)
	if err != nil {
		return err
	}
	var plan api.AllocationPlan
	_ = json.Unmarshal(raw, &plan)
	clinicGap := map[string]int{}
	for _, c := range b.Clinics {
		clinicGap[c.RegionID] = c.MinGapDays
	}
	rows := []map[string]any{}
	for _, r := range plan.RegionCoverage {
		short := r.Need - r.Delivered
		if short < 0 {
			short = 0
		}
		weeks := wavebook.Dose2Wave(0, clinicGap[r.RegionID])
		rows = append(rows, map[string]any{
			"region_id":       r.RegionID,
			"projected_cases": short * weeks,
		})
	}
	return writeJSON("/app/output/infection_projection.json", map[string]any{"wave": plan.Wave, "rows": rows})
}

func Inspect(generation int) ([]byte, error) {
	doc, err := staging.Recall(generation)
	if err != nil {
		return nil, err
	}
	return json.MarshalIndent(doc.Plan, "", "  ")
}

func SpoilageReplan(lab string, wave int) error {
	_ = os.Remove("/app/output/coldchain_audit.json")
	if err := PlanWave(lab, wave, "/app/output/allocation_plan.json"); err != nil {
		return err
	}
	return BindLanes(wave, "/app/output/allocation_plan.json", "/app/output/coldchain_audit.json")
}

func EnsureDirs() {
	_ = os.MkdirAll("/app/output", 0o755)
	_ = os.MkdirAll("/app/var", 0o755)
}
GO

/usr/local/go/bin/gofmt -w lotledger/pick.go wavebook/gap.go equitygate/floor.go coldlane/bind.go staging/plan_cache.go scopebook/ledger.go emit/plan.go
/usr/local/go/bin/go build -o /app/bin/immunoflow ./cmd/immunoflow
/app/bin/immunoflow bench reset
/app/bin/immunoflow plan-wave --lab /app/data/immunolab --wave 3 --out /app/output/allocation_plan.json
/app/bin/immunoflow bind-lanes --wave 3 --plan /app/output/allocation_plan.json --out /app/output/coldchain_audit.json
/app/bin/immunoflow schedule-doses --lab /app/data/immunolab --dose1-wave 3
/app/bin/immunoflow reconcile-equity --lab /app/data/immunolab --plan /app/output/allocation_plan.json
/app/bin/immunoflow project-infections --lab /app/data/immunolab --plan /app/output/allocation_plan.json
