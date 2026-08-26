package boiloff

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

const ambientTempC = 25.0

type Tank struct {
	TankID, TerminalID, InsulationClass string
	DiameterM, MaxLiquidHeightM         float64
}

type Reading struct {
	TankID, Timestamp                    string
	PressureKpag, LiquidTempC, VaporTempC float64
	LevelMm                              float64
}

type Transfer struct {
	TankID, Timestamp, EventType string
	MassTonnes                   float64
}

type Snapshot struct {
	TankID, Timestamp string
	GaugedMassTonnes  float64
}

type Maintenance struct {
	TankID, TimestampStart, TimestampEnd, EventType string
}

type Profile struct {
	InsulationClass         string  `json:"insulation_class"`
	HeatLeakWM2             float64 `json:"heat_leak_w_m2"`
	LngDensityKgM3          float64 `json:"lng_density_kg_m3"`
	LatentHeatKjKg          float64 `json:"latent_heat_kj_kg"`
	AllowableImbalancePct   float64 `json:"allowable_imbalance_pct"`
	ReliefPressureDropKpag  float64 `json:"relief_pressure_drop_kpag"`
}

type StageTank struct {
	TankID                string   `json:"tank_id"`
	TerminalID            string   `json:"terminal_id"`
	InsulationClass       string   `json:"insulation_class"`
	Status                string   `json:"status"`
	OpeningMassTonnes     float64  `json:"opening_mass_tonnes"`
	ClosingGaugedTonnes   float64  `json:"closing_gauged_tonnes"`
	ExpectedClosingTonnes float64  `json:"expected_closing_tonnes"`
	HeatLeakBogTonnes     float64  `json:"heat_leak_bog_tonnes"`
	ReliefBogTonnes       float64  `json:"relief_bog_tonnes"`
	TransactionDeltaTonnes float64 `json:"transaction_delta_tonnes"`
	ImbalancePct          float64  `json:"imbalance_pct"`
	Violations            []string `json:"violations"`
}

type Stage struct {
	Version    string      `json:"version"`
	SourceHash string      `json:"source_hash"`
	StageHash  string      `json:"stage_hash"`
	StageSeal  string      `json:"stage_seal"`
	Tanks      []StageTank `json:"tanks"`
}

type Action struct {
	TankID string `json:"tank_id"`
	Action string `json:"action"`
	Reason string `json:"reason"`
	Value  string `json:"value"`
}

type ReportTank struct {
	TankID                string   `json:"tank_id"`
	Status                string   `json:"status"`
	HeatLeakBogTonnes     float64  `json:"heat_leak_bog_tonnes"`
	ReliefBogTonnes       float64  `json:"relief_bog_tonnes"`
	ImbalancePct          float64  `json:"imbalance_pct"`
	Violations            []string `json:"violations"`
}

type Report struct {
	Version            string       `json:"version"`
	SourceHash         string       `json:"source_hash"`
	StageHash          string       `json:"stage_hash"`
	TotalTanks         int          `json:"total_tanks"`
	BalancedTanks      int          `json:"balanced_tanks"`
	ImbalancedTanks    int          `json:"imbalanced_tanks"`
	Tanks              []ReportTank `json:"tanks"`
	CorrectiveActions  []Action     `json:"corrective_actions"`
	ReportHash         string       `json:"report_hash"`
}

func Run() error {
	in := env("BOILOFF_INPUT_DIR", "/app/data")
	out := env("BOILOFF_OUTPUT_DIR", "/app/output")
	st := env("BOILOFF_STATE_DIR", "/app/state")
	if !abs(in) || !abs(out) || !abs(st) {
		return fmt.Errorf("directories must be absolute")
	}
	if strings.EqualFold(os.Getenv("BOILOFF_EXPORT_FROM_STAGE_ONLY"), "true") {
		var stage Stage
		b, err := os.ReadFile(filepath.Join(st, "boiloff-stage.json"))
		if err != nil {
			return err
		}
		if err := json.Unmarshal(b, &stage); err != nil {
			return err
		}
		if err := validate(stage); err != nil {
			return err
		}
		return writeReport(out, buildReport(stage))
	}
	stage, err := buildStage(in)
	if err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(st, "boiloff-stage.json"), stage); err != nil {
		return err
	}
	return writeReport(out, buildReport(stage))
}

func env(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

func abs(p string) bool { return filepath.IsAbs(p) && !strings.Contains(p, "..") }

func ts(v string) time.Time {
	t, err := time.Parse(time.RFC3339, v)
	if err != nil {
		panic(err)
	}
	return t.UTC()
}

func r3(v float64) float64 { return math.Round((v+1e-9)*1000) / 1000 }

func rows(p string) ([]map[string]string, error) {
	f, e := os.Open(p)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	rr, e := csv.NewReader(f).ReadAll()
	if e != nil {
		return nil, e
	}
	var out []map[string]string
	for _, x := range rr[1:] {
		m := map[string]string{}
		for i, h := range rr[0] {
			if i < len(x) {
				m[h] = x[i]
			}
		}
		out = append(out, m)
	}
	return out, nil
}

func fl(m map[string]string, k string) float64 {
	v, _ := strconv.ParseFloat(m[k], 64)
	return v
}

func load(in string) ([]Tank, []Reading, []Transfer, []Snapshot, []Maintenance, []Profile, error) {
	tr, e := rows(filepath.Join(in, "tanks.csv"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	rr, e := rows(filepath.Join(in, "tank_readings.csv"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	xr, e := rows(filepath.Join(in, "transfer_events.csv"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	sr, e := rows(filepath.Join(in, "inventory_snapshots.csv"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	mr, e := rows(filepath.Join(in, "maintenance_events.csv"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	var ps []Profile
	b, e := os.ReadFile(filepath.Join(in, "config", "boiloff-profiles.json"))
	if e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	if e := json.Unmarshal(b, &ps); e != nil {
		return nil, nil, nil, nil, nil, nil, e
	}
	var tanks []Tank
	for _, m := range tr {
		tanks = append(tanks, Tank{
			m["tank_id"], m["terminal_id"], m["insulation_class"],
			fl(m, "diameter_m"), fl(m, "max_liquid_height_m"),
		})
	}
	var readings []Reading
	for _, m := range rr {
		readings = append(readings, Reading{
			m["tank_id"], m["timestamp"],
			fl(m, "pressure_kpag"), fl(m, "liquid_temp_c"), fl(m, "vapor_temp_c"),
			fl(m, "level_mm"),
		})
	}
	var transfers []Transfer
	for _, m := range xr {
		transfers = append(transfers, Transfer{
			m["tank_id"], m["timestamp"], m["event_type"], fl(m, "mass_tonnes"),
		})
	}
	var snaps []Snapshot
	for _, m := range sr {
		snaps = append(snaps, Snapshot{m["tank_id"], m["timestamp"], fl(m, "gauged_mass_tonnes")})
	}
	var maint []Maintenance
	for _, m := range mr {
		maint = append(maint, Maintenance{
			m["tank_id"], m["timestamp_start"], m["timestamp_end"], m["event_type"],
		})
	}
	return tanks, readings, transfers, snaps, maint, ps, nil
}

func sourceHash(in string) (string, error) {
	h := sha256.New()
	for _, rel := range []string{
		"tanks.csv",
		"tank_readings.csv",
		"transfer_events.csv",
		"inventory_snapshots.csv",
		"maintenance_events.csv",
		"config/boiloff-profiles.json",
	} {
		b, e := os.ReadFile(filepath.Join(in, rel))
		if e != nil {
			return "", e
		}
		h.Write([]byte(rel))
		h.Write([]byte{0})
		h.Write(b)
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func hjson(v any) string {
	b, _ := json.Marshal(v)
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])
}

func prof(tank Tank, ps []Profile) Profile {
	for _, p := range ps {
		if p.InsulationClass == tank.InsulationClass {
			return p
		}
	}
	return ps[0]
}

func wettedAreaM2(diameterM, levelMm float64) float64 {
	h := levelMm / 1000.0
	return math.Pi*diameterM*diameterM/4.0 + math.Pi*diameterM*h
}

func deltaTKelvin(liquidTempC float64) float64 {
	ambientK := ambientTempC + 273.15
	liquidK := liquidTempC + 273.15
	return ambientK - liquidK
}

func bogRateTonnesPerHour(tank Tank, r Reading, p Profile) float64 {
	area := wettedAreaM2(tank.DiameterM, r.LevelMm)
	dt := deltaTKelvin(r.LiquidTempC)
	if dt <= 0 {
		return 0
	}
	qW := p.HeatLeakWM2 * area * dt
	kgPerS := qW / (p.LatentHeatKjKg * 1000.0)
	return r3(kgPerS * 3600.0 / 1000.0)
}

func maintenanceIntervals(tankID string, maint []Maintenance) [][2]time.Time {
	var out [][2]time.Time
	for _, m := range maint {
		if m.TankID != tankID {
			continue
		}
		out = append(out, [2]time.Time{ts(m.TimestampStart), ts(m.TimestampEnd)})
	}
	return out
}

func readingExcluded(t time.Time, intervals [][2]time.Time) bool {
	for _, iv := range intervals {
		if !t.Before(iv[0]) && t.Before(iv[1]) {
			return true
		}
	}
	return false
}

func heatLeakBogTonnes(tank Tank, readings []Reading, maint []Maintenance, p Profile) float64 {
	intervals := maintenanceIntervals(tank.TankID, maint)
	var eligible []Reading
	for _, r := range readings {
		if r.TankID != tank.TankID {
			continue
		}
		if readingExcluded(ts(r.Timestamp), intervals) {
			continue
		}
		eligible = append(eligible, r)
	}
	if len(eligible) == 0 {
		return 0
	}
	sort.Slice(eligible, func(i, j int) bool {
		return ts(eligible[i].Timestamp).Before(ts(eligible[j].Timestamp))
	})
	if len(eligible) == 1 {
		return r3(bogRateTonnesPerHour(tank, eligible[0], p) * 0.001)
	}
	total := 0.0
	for i := 0; i < len(eligible)-1; i++ {
		t0 := ts(eligible[i].Timestamp)
		t1 := ts(eligible[i+1].Timestamp)
		dtH := t1.Sub(t0).Hours()
		r0 := bogRateTonnesPerHour(tank, eligible[i], p)
		r1 := bogRateTonnesPerHour(tank, eligible[i+1], p)
		total += (r0 + r1) / 2.0 * dtH
	}
	return r3(total)
}

func reliefBogTonnes(tankID string, transfers []Transfer) float64 {
	sum := 0.0
	for _, x := range transfers {
		if x.TankID == tankID && x.EventType == "relief" {
			sum += x.MassTonnes
		}
	}
	return r3(sum)
}

func transactionDelta(tankID string, transfers []Transfer) float64 {
	delta := 0.0
	for _, x := range transfers {
		if x.TankID != tankID {
			continue
		}
		switch x.EventType {
		case "delivery":
			delta += x.MassTonnes
		case "withdrawal":
			delta -= x.MassTonnes
		case "regas":
			delta -= x.MassTonnes
		}
	}
	return r3(delta)
}

func snapshotsForTank(tankID string, snaps []Snapshot) (opening, closing Snapshot) {
	var mine []Snapshot
	for _, s := range snaps {
		if s.TankID == tankID {
			mine = append(mine, s)
		}
	}
	sort.Slice(mine, func(i, j int) bool {
		return ts(mine[i].Timestamp).Before(ts(mine[j].Timestamp))
	})
	if len(mine) == 0 {
		return Snapshot{}, Snapshot{}
	}
	return mine[0], mine[len(mine)-1]
}

func violations(p Profile, imbalancePct, heatLeak, relief float64) []string {
	v := []string{}
	if math.Abs(imbalancePct) > p.AllowableImbalancePct {
		v = append(v, "IMBALANCE_HIGH")
	}
	if heatLeak > 120.0 {
		v = append(v, "BOG_RATE_HIGH")
	}
	if relief > 15.0 {
		v = append(v, "RELIEF_EXCESSIVE")
	}
	return v
}

func buildStage(in string) (Stage, error) {
	tanks, readings, transfers, snaps, maint, profiles, e := load(in)
	if e != nil {
		return Stage{}, e
	}
	sort.Slice(tanks, func(i, j int) bool { return tanks[i].TankID < tanks[j].TankID })
	sh, _ := sourceHash(in)
	var st []StageTank
	for _, tank := range tanks {
		p := prof(tank, profiles)
		open, close := snapshotsForTank(tank.TankID, snaps)
		heat := heatLeakBogTonnes(tank, readings, maint, p)
		relief := reliefBogTonnes(tank.TankID, transfers)
		delta := transactionDelta(tank.TankID, transfers)
		expected := r3(open.GaugedMassTonnes + delta - heat - relief)
		imbalance := 0.0
		if close.GaugedMassTonnes != 0 {
			imbalance = r3((close.GaugedMassTonnes - expected) / close.GaugedMassTonnes * 100.0)
		}
		v := violations(p, imbalance, heat, relief)
		status := "balanced"
		if len(v) > 0 {
			status = "imbalanced"
		}
		st = append(st, StageTank{
			tank.TankID, tank.TerminalID, tank.InsulationClass, status,
			open.GaugedMassTonnes, close.GaugedMassTonnes, expected,
			heat, relief, delta, imbalance, v,
		})
	}
	stage := Stage{"boiloff-stage-v1", sh, "", "", st}
	stage.StageHash = hjson(struct {
		Version    string      `json:"version"`
		SourceHash string      `json:"source_hash"`
		Tanks      []StageTank `json:"tanks"`
	}{stage.Version, stage.SourceHash, stage.Tanks})
	stage.StageSeal = seal(stage)
	return stage, nil
}

func actions(t StageTank) []Action {
	var out []Action
	for _, v := range t.Violations {
		switch v {
		case "IMBALANCE_HIGH":
			out = append(out, Action{t.TankID, "investigate_gauging", "inventory imbalance above profile tolerance", fmt.Sprintf("%.3f", t.ImbalancePct)})
		case "BOG_RATE_HIGH":
			out = append(out, Action{t.TankID, "inspect_insulation", "heat-leak boil-off above review threshold", fmt.Sprintf("%.3f", t.HeatLeakBogTonnes)})
		case "RELIEF_EXCESSIVE":
			out = append(out, Action{t.TankID, "review_relief_valve", "relief vent mass above terminal limit", fmt.Sprintf("%.3f", t.ReliefBogTonnes)})
		}
	}
	return out
}

func buildReport(st Stage) Report {
	rp := Report{
		Version:           "boiloff-report-v1",
		SourceHash:        st.SourceHash,
		StageHash:         st.StageHash,
		Tanks:             []ReportTank{},
		CorrectiveActions: []Action{},
	}
	for _, t := range st.Tanks {
		rp.TotalTanks++
		if t.Status == "balanced" {
			rp.BalancedTanks++
		} else {
			rp.ImbalancedTanks++
		}
		rp.Tanks = append(rp.Tanks, ReportTank{
			t.TankID, t.Status, t.HeatLeakBogTonnes, t.ReliefBogTonnes, t.ImbalancePct, t.Violations,
		})
		rp.CorrectiveActions = append(rp.CorrectiveActions, actions(t)...)
	}
	sort.Slice(rp.CorrectiveActions, func(i, j int) bool {
		if rp.CorrectiveActions[i].TankID == rp.CorrectiveActions[j].TankID {
			return rp.CorrectiveActions[i].Action < rp.CorrectiveActions[j].Action
		}
		return rp.CorrectiveActions[i].TankID < rp.CorrectiveActions[j].TankID
	})
	rp.ReportHash = hjson(struct {
		Version           string       `json:"version"`
		SourceHash        string       `json:"source_hash"`
		StageHash         string       `json:"stage_hash"`
		TotalTanks        int          `json:"total_tanks"`
		BalancedTanks     int          `json:"balanced_tanks"`
		ImbalancedTanks   int          `json:"imbalanced_tanks"`
		Tanks             []ReportTank `json:"tanks"`
		CorrectiveActions []Action     `json:"corrective_actions"`
	}{rp.Version, rp.SourceHash, rp.StageHash, rp.TotalTanks, rp.BalancedTanks, rp.ImbalancedTanks, rp.Tanks, rp.CorrectiveActions})
	return rp
}

func seal(st Stage) string {
	return hjson(struct {
		Version    string      `json:"version"`
		SourceHash string      `json:"source_hash"`
		StageHash  string      `json:"stage_hash"`
		Tanks      []StageTank `json:"tanks"`
	}{st.Version, st.SourceHash, st.StageHash, st.Tanks})
}

func validate(st Stage) error {
	if st.Version != "boiloff-stage-v1" {
		return fmt.Errorf("bad stage version")
	}
	if st.StageHash != hjson(struct {
		Version    string      `json:"version"`
		SourceHash string      `json:"source_hash"`
		Tanks      []StageTank `json:"tanks"`
	}{st.Version, st.SourceHash, st.Tanks}) {
		return fmt.Errorf("stage hash mismatch")
	}
	if st.StageSeal != seal(st) {
		return fmt.Errorf("stage seal mismatch")
	}
	return nil
}

func writeJSON(path string, v any) error {
	os.MkdirAll(filepath.Dir(path), 0755)
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	return os.WriteFile(path, append(b, '\n'), 0644)
}

func writeReport(out string, r Report) error {
	if e := writeJSON(filepath.Join(out, "boiloff-report.json"), r); e != nil {
		return e
	}
	os.MkdirAll(out, 0755)
	f, e := os.Create(filepath.Join(out, "corrective-actions.tsv"))
	if e != nil {
		return e
	}
	defer f.Close()
	w := csv.NewWriter(f)
	w.Comma = '\t'
	_ = w.Write([]string{"tank_id", "action", "reason", "value"})
	for _, a := range r.CorrectiveActions {
		_ = w.Write([]string{a.TankID, a.Action, a.Reason, a.Value})
	}
	w.Flush()
	return w.Error()
}
