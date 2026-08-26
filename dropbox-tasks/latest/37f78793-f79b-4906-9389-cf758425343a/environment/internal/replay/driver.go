package replay

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"mdllab/internal/aura"
	"mdllab/internal/persist"
	"mdllab/internal/pulse"
	"mdllab/internal/settle"
)

var (
	EnvRoot = envRoot()
	EvDir   = filepath.Join(EnvRoot, "fixtures", "ev_bins")
)

func envRoot() string {
	if v := os.Getenv("MDL_ENV_ROOT"); v != "" {
		return v
	}
	return "/app/environment"
}

type ScenarioSpec struct {
	Codename   string `json:"codename"`
	EvBin      string `json:"ev_bin"`
	BandLo     int    `json:"band_lo"`
	BandHi     int    `json:"band_hi"`
	Combo      bool   `json:"combo"`
	MagSeed    int    `json:"mag_seed"`
	DurSeed    int    `json:"dur_seed"`
	ComboDepth int    `json:"combo_depth"`
	EntityA    int    `json:"entity_a"`
	EntityB    int    `json:"entity_b"`
}

type Violation struct {
	Codename  string `json:"codename"`
	Profile   string `json:"profile"`
	ComboLen  int    `json:"combo_len"`
	ReasonCode string `json:"reason_code"`
}

func LoadCoef() (aura.LaneCoef, error) {
	raw, err := os.ReadFile(filepath.Join(EnvRoot, "docs", "lane_coef.json"))
	if err != nil {
		return aura.LaneCoef{}, err
	}
	var rawMap map[string]int
	if err := json.Unmarshal(raw, &rawMap); err != nil {
		return aura.LaneCoef{}, err
	}
	return aura.LaneCoef{Primary: rawMap["primary"], Secondary: rawMap["secondary"]}, nil
}

func LoadScenario(path string) (ScenarioSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ScenarioSpec{}, err
	}
	var spec ScenarioSpec
	if err := json.Unmarshal(raw, &spec); err != nil {
		return ScenarioSpec{}, err
	}
	return spec, nil
}

func ParseEvBytes(raw []byte) (payload []byte, magSeed, durSeed, entityA, entityB, comboDepth int, activations []int, err error) {
	if len(raw) < 12 || string(raw[:4]) != "EVB\x01" {
		return nil, 0, 0, 0, 0, 0, nil, errInvalid("invalid ev bin header")
	}
	magSeed = int(raw[4])
	durSeed = int(raw[5])
	entityA = int(raw[6])
	entityB = int(raw[7])
	comboDepth = int(raw[8])
	payload = raw[12:]
	limit := comboDepth
	if limit > len(payload) {
		limit = len(payload)
	}
	activations = make([]int, 0, limit)
	for i := 0; i < limit; i++ {
		activations = append(activations, int(payload[i])%16)
	}
	return payload, magSeed, durSeed, entityA, entityB, comboDepth, activations, nil
}

type simpleError string

func (e simpleError) Error() string { return string(e) }
func errInvalid(msg string) error { return simpleError(msg) }

func EnumerateCombos(activations []int, depthLimit int) [][]int {
	if len(activations) == 0 {
		return [][]int{{}}
	}
	combos := [][]int{{}}
	frontier := [][]int{{}}
	for len(frontier) > 0 && len(combos) < depthLimit+1 {
		current := frontier[0]
		frontier = frontier[1:]
		if len(current) >= depthLimit {
			continue
		}
		limit := 3
		if limit > len(activations) {
			limit = len(activations)
		}
		for i := 0; i < limit; i++ {
			nxt := append(append([]int{}, current...), activations[i])
			combos = append(combos, nxt)
			frontier = append(frontier, nxt)
		}
	}
	if len(combos) > depthLimit+1 {
		combos = combos[:depthLimit+1]
	}
	return combos
}

func SimulateRow(spec ScenarioSpec, profile pulse.TickProfile, combo []int, depthLimit int, coef aura.LaneCoef) (material []byte, bandLo, bandHi, rowCount int, violations []Violation, err error) {
	raw, err := os.ReadFile(filepath.Join(EvDir, spec.EvBin))
	if err != nil {
		return nil, 0, 0, 0, nil, err
	}
	payload, magSeed, durSeed, entityA, entityB, _, _, err := ParseEvBytes(raw)
	if err != nil {
		return nil, 0, 0, 0, nil, err
	}
	canonical := RebuildCanonical(payload, magSeed, durSeed, coef)

	period := durSeed%5 + 2
	if period < 2 {
		period = 2
	}
	sched := pulse.TickSched{Tick: magSeed, PulsePeriod: period, PendingDamage: len(combo)}
	iframe := pulse.IFrameCtr{Active: durSeed%2 == 1, OverlapTicks: durSeed % 4}
	plan := planForRow(sched, profile, iframe)

	if profile == pulse.ProfileLoose && iframe.Active && plan.FireNow {
		violations = append(violations, Violation{
			Codename:   spec.Codename,
			Profile:    profile.Label(),
			ComboLen:   len(combo),
			ReasonCode: "pulse_overlap",
		})
	}

	// Match prior lab: hp_a = max(0, 100 - sum(combo) - (0 if deferred else pulse_count))
	penalty := 0
	if plan.Deferred == 0 {
		penalty = plan.PulseCount
	}
	hpA := 100 - sumInts(combo) - penalty
	if hpA < 0 {
		hpA = 0
	}
	hpB := 100 - magSeed - durSeed - len(combo)
	if hpB < 0 {
		hpB = 0
	}
	state := settle.OutcomeState{HPA: hpA, HPB: hpB, Settled: false, WinnerID: -1}
	order := [2]int{entityA, entityB}
	if spec.Combo {
		order = [2]int{entityB, entityA}
	}
	actors := settle.ActorPair{EntityA: entityA, EntityB: entityB, ActionOrder: order}
	verdict := closeLethal(state, actors, len(combo)+depthLimit)

	if state.HPA <= 0 && state.HPB <= 0 && verdict.State.Settled {
		expected := entityA
		if entityB < expected {
			expected = entityB
		}
		if verdict.State.WinnerID != expected {
			violations = append(violations, Violation{
				Codename:   spec.Codename,
				Profile:    profile.Label(),
				ComboLen:   len(combo),
				ReasonCode: "tie_order",
			})
		}
	}

	stored, err := persist.LoadState()
	if err != nil {
		return nil, 0, 0, 0, nil, err
	}
	if stored.Poisoned {
		violations = append(violations, Violation{
			Codename:   spec.Codename,
			Profile:    profile.Label(),
			ComboLen:   len(combo),
			ReasonCode: "state_poison",
		})
	}
	carry := stored.PulseCarry
	residue := (carry + plan.PulseCount + magSeed) % 256
	if err := persist.SaveState(persist.SettleState{Poisoned: stored.Poisoned, PulseCarry: residue}); err != nil {
		return nil, 0, 0, 0, nil, err
	}
	_ = persist.AppendJournal(persist.JournalLine{
		Codename: spec.Codename,
		Profile:  profile.Label(),
		Residue:  residue,
	})

	slotLo := spec.BandLo
	slotHi := spec.BandHi
	if len(combo) > 0 {
		slotLo = minInt(combo...)
		slotHi = maxInt(combo...)
	}
	entropy := (sumInts(combo) + residue + magSeed + durSeed) % 256
	bandLo = maxInt(spec.BandLo, minInt(slotLo, entropy))
	bandHi = minInt(spec.BandHi, maxInt(slotHi, entropy+1, bandLo+1))
	rowCount = len(combo) + plan.PulseCount + 1

	material = append(append([]byte{}, canonical...), byte(residue))
	for _, c := range combo {
		material = append(material, byte(c))
	}
	return material, bandLo, bandHi, rowCount, violations, nil
}

func RunManifest(spec ScenarioSpec, profile pulse.TickProfile, depthLimit int, coef aura.LaneCoef) (map[string]any, error) {
	raw, err := os.ReadFile(filepath.Join(EvDir, spec.EvBin))
	if err != nil {
		return nil, err
	}
	_, magSeed, durSeed, _, _, _, activations, err := ParseEvBytes(raw)
	if err != nil {
		return nil, err
	}
	combos := EnumerateCombos(activations, depthLimit)
	var violations []Violation
	var digests []string
	bandLo := spec.BandLo
	bandHi := spec.BandHi
	rowCount := 0

	for _, combo := range combos {
		material, lo, hi, rows, comboViolations, serr := SimulateRow(spec, profile, combo, depthLimit, coef)
		if serr != nil {
			return nil, serr
		}
		violations = append(violations, comboViolations...)
		sum := sha256.Sum256(material)
		digests = append(digests, hex.EncodeToString(sum[:]))
		if lo > bandLo {
			bandLo = lo
		}
		if hi < bandHi {
			bandHi = hi
		}
		if rows > rowCount {
			rowCount = rows
		}
	}

	sortedDigests := append([]string{}, digests...)
	sort.Strings(sortedDigests)
	joined := ""
	for _, d := range sortedDigests {
		joined += d
	}
	cross := sha256.Sum256([]byte(joined))

	canonical := RebuildCanonical(raw[12:], magSeed, durSeed, coef)
	violMaps := []map[string]any{}
	for _, v := range violations {
		violMaps = append(violMaps, map[string]any{
			"codename":    v.Codename,
			"profile":     v.Profile,
			"combo_len":   v.ComboLen,
			"reason_code": v.ReasonCode,
		})
	}

	return map[string]any{
		"codename":        spec.Codename,
		"profile":         profile.Label(),
		"digest_hex":      hex.EncodeToString(cross[:]),
		"violation_rows":  len(violations),
		"violations":      violMaps,
		"band_lo":         bandLo,
		"band_hi":         bandHi,
		"row_count":       rowCount,
		"event_bytes_len": len(canonical),
	}, nil
}

func sumInts(vals []int) int {
	s := 0
	for _, v := range vals {
		s += v
	}
	return s
}

func minInt(vals ...int) int {
	m := vals[0]
	for _, v := range vals[1:] {
		if v < m {
			m = v
		}
	}
	return m
}

func maxInt(vals ...int) int {
	m := vals[0]
	for _, v := range vals[1:] {
		if v > m {
			m = v
		}
	}
	return m
}
