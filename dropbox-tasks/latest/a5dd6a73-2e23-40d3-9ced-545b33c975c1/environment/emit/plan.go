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
	delivered := map[string]int{}
	assign := []api.LotAssignment{}
	for _, region := range regions {
		eligible := []api.Lot{}
		for _, lot := range b.Lots {
			if lot.TempBand == region.StorageTemp {
				eligible = append(eligible, lot)
			}
		}
		picked, err := lotledger.PickLots(eligible, region.DemandDose1, b.Config.VialSize)
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
		d := eq.RegionDelivered[r.RegionID]
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
	c := support.LoadCustoms()
	for _, r := range b.Routes {
		c.TotalDelayDays += r.CustomsDelayDays
		c.ByRegion[r.RegionID] += r.CustomsDelayDays
	}
	_ = support.SaveCustoms(c)
	_ = staging.Store(staging.CacheDoc{Generation: scopebook.Load().Generation, Wave: wave, Plan: plan})
	_ = writeJSON("/app/output/equity_rollup.json", map[string]any{"region_delivered": plan.RegionCoverage, "equity_met": plan.EquityMet})
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
		_ = clinicGap[r.RegionID]
		rows = append(rows, map[string]any{
			"region_id":       r.RegionID,
			"projected_cases": (r.Need - r.Delivered) * 2,
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
