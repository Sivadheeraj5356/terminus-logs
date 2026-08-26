package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
)

const (
	inputPath  = "/workspace/task_file/colony.json"
	outputPath = "/workspace/colony_plan.json"
)

type Capacities struct {
	Battery int `json:"battery"`
	Oxygen  int `json:"oxygen"`
	Water   int `json:"water"`
	Morale  int `json:"morale"`
	Hull    int `json:"hull"`
	Wear    int `json:"wear"`
	Fatigue int `json:"fatigue"`
}

type State struct {
	Battery int `json:"battery"`
	Oxygen  int `json:"oxygen"`
	Water   int `json:"water"`
	Morale  int `json:"morale"`
	Dust    int `json:"dust"`
	Hull    int `json:"hull"`
	Wear    int `json:"wear"`
	Insight int `json:"insight"`
	Fatigue int `json:"fatigue"`
}

type Targets struct {
	Insight int `json:"insight"`
	Hull    int `json:"hull"`
	Morale  int `json:"morale"`
}

type Sol struct {
	ID       string `json:"id"`
	Sunlight int    `json:"sunlight"`
	Hazard   string `json:"hazard"`
}

type Input struct {
	CaseID         string     `json:"case_id"`
	Ruleset        string     `json:"ruleset"`
	Population     int        `json:"population"`
	Regolith       string     `json:"regolith"`
	Recycler       string     `json:"recycler"`
	AllowEmergency bool       `json:"allow_emergency"`
	Capacities     Capacities `json:"capacities"`
	Initial        State      `json:"initial"`
	Targets        Targets    `json:"targets"`
	Sols           []Sol      `json:"sols"`
}

type Decision struct {
	Sol          int    `json:"sol"`
	ID           string `json:"id"`
	Ration       string `json:"ration"`
	Directive    string `json:"directive"`
	HazardResult string `json:"hazard_result"`
}

type SolarFlow struct {
	Raw   int `json:"raw"`
	Added int `json:"added"`
	Spill int `json:"spill"`
}

type DirectiveFlow struct {
	BatterySpent int `json:"battery_spent"`
	OxygenAdded  int `json:"oxygen_added"`
	WaterSpent   int `json:"water_spent"`
	WaterAdded   int `json:"water_added"`
	HullAdded    int `json:"hull_added"`
	DustRemoved  int `json:"dust_removed"`
	WearDelta    int `json:"wear_delta"`
	InsightAdded int `json:"insight_added"`
	FatigueDelta int `json:"fatigue_delta"`
}

type HazardFlow struct {
	OxygenSpent int `json:"oxygen_spent"`
	HullLost    int `json:"hull_lost"`
	MoraleLost  int `json:"morale_lost"`
	WearAdded   int `json:"wear_added"`
}

type RationFlow struct {
	OxygenSpent  int `json:"oxygen_spent"`
	WaterSpent   int `json:"water_spent"`
	MoraleDelta  int `json:"morale_delta"`
	FatigueAdded int `json:"fatigue_added"`
}

type RecycleFlow struct {
	Resource string `json:"resource"`
	Added    int    `json:"added"`
	Spill    int    `json:"spill"`
}

type LedgerRow struct {
	Sol       int           `json:"sol"`
	Start     State         `json:"start"`
	Solar     SolarFlow     `json:"solar"`
	Directive DirectiveFlow `json:"directive"`
	Hazard    HazardFlow    `json:"hazard"`
	Ration    RationFlow    `json:"ration"`
	Recycle   RecycleFlow   `json:"recycle"`
	End       State         `json:"end"`
}

type Objective struct {
	MinimumSafety int    `json:"minimum_safety"`
	FinalInsight  int    `json:"final_insight"`
	FinalMorale   int    `json:"final_morale"`
	FinalReserves int    `json:"final_reserves"`
	FinalWear     int    `json:"final_wear"`
	EmergencySols int    `json:"emergency_sols"`
	PlanKey       string `json:"plan_key"`
}

type Output struct {
	Status    string      `json:"status"`
	Ruleset   string      `json:"ruleset"`
	Decisions []Decision  `json:"decisions"`
	Ledger    []LedgerRow `json:"ledger"`
	Objective *Objective  `json:"objective"`
}

type record struct {
	State       State
	MinSafety   int
	Emergencies int
	PlanKey     string
	Decisions   []Decision
	Ledger      []LedgerRow
}

var directives = []string{"rest", "sweep", "mine", "electrolyze", "service", "patch", "brace", "research"}

func main() {
	_ = os.Remove(outputPath)
	in, err := loadInput(inputPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	out := solve(in)
	data, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	data = append(data, '\n')
	tmp := outputPath + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := os.Rename(tmp, outputPath); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}

func loadInput(path string) (Input, error) {
	var in Input
	data, err := os.ReadFile(path)
	if err != nil {
		return in, err
	}
	if err := checkJSONShape(data); err != nil {
		return in, err
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		return in, err
	}
	if err := ensureEOF(dec); err != nil {
		return in, err
	}
	if err := validateInput(in); err != nil {
		return in, err
	}
	return in, nil
}

func ensureEOF(dec *json.Decoder) error {
	var extra any
	if err := dec.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return errors.New("trailing JSON value")
		}
		return err
	}
	return nil
}

func checkJSONShape(data []byte) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	value, err := readUnique(dec)
	if err != nil {
		return err
	}
	if _, ok := value.(map[string]any); !ok {
		return errors.New("top-level JSON must be an object")
	}
	if err := ensureEOF(dec); err != nil {
		return err
	}
	top := value.(map[string]any)
	if !exactKeys(top, "case_id", "ruleset", "population", "regolith", "recycler", "allow_emergency", "capacities", "initial", "targets", "sols") {
		return errors.New("invalid top-level fields")
	}
	if !nestedKeys(top["capacities"], "battery", "oxygen", "water", "morale", "hull", "wear", "fatigue") {
		return errors.New("invalid capacities fields")
	}
	if !nestedKeys(top["initial"], "battery", "oxygen", "water", "morale", "dust", "hull", "wear", "insight", "fatigue") {
		return errors.New("invalid initial fields")
	}
	if !nestedKeys(top["targets"], "insight", "hull", "morale") {
		return errors.New("invalid targets fields")
	}
	sols, ok := top["sols"].([]any)
	if !ok {
		return errors.New("sols must be an array")
	}
	for _, sol := range sols {
		if !nestedKeys(sol, "id", "sunlight", "hazard") {
			return errors.New("invalid sol fields")
		}
	}
	return nil
}

func readUnique(dec *json.Decoder) (any, error) {
	tok, err := dec.Token()
	if err != nil {
		return nil, err
	}
	delim, ok := tok.(json.Delim)
	if !ok {
		return tok, nil
	}
	if delim == '[' {
		items := []any{}
		for dec.More() {
			item, err := readUnique(dec)
			if err != nil {
				return nil, err
			}
			items = append(items, item)
		}
		if _, err := dec.Token(); err != nil {
			return nil, err
		}
		return items, nil
	}
	if delim != '{' {
		return nil, errors.New("unexpected JSON delimiter")
	}
	object := map[string]any{}
	for dec.More() {
		keyToken, err := dec.Token()
		if err != nil {
			return nil, err
		}
		key, ok := keyToken.(string)
		if !ok {
			return nil, errors.New("object key is not a string")
		}
		if _, exists := object[key]; exists {
			return nil, fmt.Errorf("duplicate key %q", key)
		}
		item, err := readUnique(dec)
		if err != nil {
			return nil, err
		}
		object[key] = item
	}
	if _, err := dec.Token(); err != nil {
		return nil, err
	}
	return object, nil
}

func exactKeys(object map[string]any, names ...string) bool {
	if len(object) != len(names) {
		return false
	}
	for _, name := range names {
		if _, ok := object[name]; !ok {
			return false
		}
	}
	return true
}

func nestedKeys(value any, names ...string) bool {
	object, ok := value.(map[string]any)
	return ok && exactKeys(object, names...)
}

func validateInput(in Input) error {
	if in.CaseID == "" || (in.Ruleset != "selene-1" && in.Ruleset != "selene-2") {
		return errors.New("invalid identity or ruleset")
	}
	if in.Population < 1 || in.Population > 4 || !oneOf(in.Regolith, "dry", "volatile") || !oneOf(in.Recycler, "off", "oxygen", "water") {
		return errors.New("invalid campaign mode")
	}
	capValues := []int{in.Capacities.Battery, in.Capacities.Oxygen, in.Capacities.Water, in.Capacities.Morale, in.Capacities.Hull, in.Capacities.Wear, in.Capacities.Fatigue}
	for _, value := range capValues {
		if value < 1 || value > 30 {
			return errors.New("capacity out of range")
		}
	}
	s := in.Initial
	if s.Battery < 0 || s.Battery > in.Capacities.Battery || s.Oxygen <= 0 || s.Oxygen > in.Capacities.Oxygen || s.Water <= 0 || s.Water > in.Capacities.Water || s.Morale <= 0 || s.Morale > in.Capacities.Morale || s.Hull <= 0 || s.Hull > in.Capacities.Hull || s.Wear < 0 || s.Wear > in.Capacities.Wear || s.Fatigue < 0 || s.Fatigue > in.Capacities.Fatigue || s.Dust < 0 || s.Dust > 30 || s.Insight < 0 || s.Insight > 30 {
		return errors.New("initial state out of range")
	}
	if in.Targets.Insight < 0 || in.Targets.Insight > 30 || in.Targets.Hull < 0 || in.Targets.Hull > in.Capacities.Hull || in.Targets.Morale < 0 || in.Targets.Morale > in.Capacities.Morale {
		return errors.New("target out of range")
	}
	if len(in.Sols) > 10 {
		return errors.New("too many sols")
	}
	ids := map[string]bool{}
	for _, sol := range in.Sols {
		if sol.ID == "" || ids[sol.ID] || sol.Sunlight < 0 || sol.Sunlight > 12 || !oneOf(sol.Hazard, "none", "flare", "impact", "quake") {
			return errors.New("invalid sol")
		}
		ids[sol.ID] = true
	}
	return nil
}

func oneOf(value string, choices ...string) bool {
	for _, choice := range choices {
		if value == choice {
			return true
		}
	}
	return false
}

func solve(in Input) Output {
	initialSafety := min4(in.Initial.Oxygen, in.Initial.Water, in.Initial.Morale, in.Initial.Hull)
	initialMin := 31
	if len(in.Sols) == 0 {
		initialMin = initialSafety
	}
	records := map[State][]record{
		in.Initial: {{
			State: in.Initial, MinSafety: initialMin, Decisions: []Decision{}, Ledger: []LedgerRow{},
		}},
	}
	for index, sol := range in.Sols {
		next := map[State][]record{}
		for _, variants := range records {
			for _, current := range variants {
				rations := []string{"full", "conserve"}
				if in.AllowEmergency {
					rations = append(rations, "emergency")
				}
				for _, ration := range rations {
					for _, directive := range directives {
						updated, decision, ledger, ok := transition(in, current.State, sol, index+1, ration, directive)
						if !ok {
							continue
						}
						safety := min4(updated.Oxygen, updated.Water, updated.Morale, updated.Hull)
						minSafety := current.MinSafety
						if safety < minSafety {
							minSafety = safety
						}
						emergencies := current.Emergencies
						if ration == "emergency" {
							emergencies++
						}
						token := ration + ":" + directive
						planKey := token
						if current.PlanKey != "" {
							planKey = current.PlanKey + "," + token
						}
						candidate := record{
							State: updated, MinSafety: minSafety, Emergencies: emergencies, PlanKey: planKey,
							Decisions: appendCopy(current.Decisions, decision), Ledger: appendCopy(current.Ledger, ledger),
						}
						next[updated] = retainPareto(next[updated], candidate)
					}
				}
			}
		}
		records = next
	}
	var best record
	found := false
	for _, variants := range records {
		for _, candidate := range variants {
			if candidate.State.Insight < in.Targets.Insight || candidate.State.Hull < in.Targets.Hull || candidate.State.Morale < in.Targets.Morale {
				continue
			}
			if !found || better(candidate, best) {
				best = candidate
				found = true
			}
		}
	}
	if !found {
		return Output{Status: "impossible", Ruleset: in.Ruleset, Decisions: []Decision{}, Ledger: []LedgerRow{}, Objective: nil}
	}
	objective := &Objective{
		MinimumSafety: best.MinSafety,
		FinalInsight:  best.State.Insight,
		FinalMorale:   best.State.Morale,
		FinalReserves: best.State.Battery + best.State.Oxygen + best.State.Water,
		FinalWear:     best.State.Wear,
		EmergencySols: best.Emergencies,
		PlanKey:       best.PlanKey,
	}
	return Output{Status: "feasible", Ruleset: in.Ruleset, Decisions: best.Decisions, Ledger: best.Ledger, Objective: objective}
}

func retainPareto(records []record, candidate record) []record {
	for _, existing := range records {
		if existing.MinSafety >= candidate.MinSafety && existing.Emergencies <= candidate.Emergencies && existing.PlanKey <= candidate.PlanKey {
			return records
		}
	}
	kept := records[:0]
	for _, existing := range records {
		if candidate.MinSafety >= existing.MinSafety && candidate.Emergencies <= existing.Emergencies && candidate.PlanKey <= existing.PlanKey {
			continue
		}
		kept = append(kept, existing)
	}
	return append(kept, candidate)
}

func appendCopy[T any](source []T, value T) []T {
	result := make([]T, len(source), len(source)+1)
	copy(result, source)
	return append(result, value)
}

func better(a, b record) bool {
	av := []int{a.MinSafety, a.State.Insight, a.State.Morale, a.State.Battery + a.State.Oxygen + a.State.Water, -a.State.Wear, -a.Emergencies}
	bv := []int{b.MinSafety, b.State.Insight, b.State.Morale, b.State.Battery + b.State.Oxygen + b.State.Water, -b.State.Wear, -b.Emergencies}
	for i := range av {
		if av[i] != bv[i] {
			return av[i] > bv[i]
		}
	}
	return a.PlanKey < b.PlanKey
}

func transition(in Input, start State, sol Sol, number int, ration, directive string) (State, Decision, LedgerRow, bool) {
	state := start
	row := LedgerRow{Sol: number, Start: start, Recycle: RecycleFlow{Resource: in.Recycler}}
	penalty := state.Dust
	if in.Ruleset == "selene-2" {
		penalty = (state.Dust + 1) / 2
	}
	row.Solar.Raw = max(0, sol.Sunlight-penalty)
	row.Solar.Added = min(row.Solar.Raw, in.Capacities.Battery-state.Battery)
	row.Solar.Spill = row.Solar.Raw - row.Solar.Added
	state.Battery += row.Solar.Added
	if !applyDirective(in, &state, directive, &row.Directive) {
		return State{}, Decision{}, LedgerRow{}, false
	}
	braced := directive == "brace"
	if !applyHazard(in, &state, sol.Hazard, braced, &row.Hazard) {
		return State{}, Decision{}, LedgerRow{}, false
	}
	if !applyRation(in, &state, ration, &row.Ration) {
		return State{}, Decision{}, LedgerRow{}, false
	}
	applyRecycler(in, &state, &row.Recycle)
	if !validEnd(in, state) {
		return State{}, Decision{}, LedgerRow{}, false
	}
	row.End = state
	decision := Decision{Sol: number, ID: sol.ID, Ration: ration, Directive: directive, HazardResult: hazardResult(sol.Hazard, braced)}
	return state, decision, row, true
}

func applyDirective(in Input, state *State, name string, flow *DirectiveFlow) bool {
	spendBattery := func(amount int) bool {
		if state.Battery < amount {
			return false
		}
		state.Battery -= amount
		flow.BatterySpent = amount
		return true
	}
	fatigueDelta := 0
	switch name {
	case "rest":
		fatigueDelta = -2
	case "sweep":
		if state.Dust <= 0 || !spendBattery(1) {
			return false
		}
		amount := 2
		if in.Ruleset == "selene-2" {
			amount = 3
		}
		flow.DustRemoved = min(amount, state.Dust)
		state.Dust -= flow.DustRemoved
		fatigueDelta = 1
	case "mine":
		wear := 2
		yield := 5
		if in.Regolith == "volatile" {
			wear = 3
			yield = 7
		}
		if state.Wear+wear > in.Capacities.Wear || !spendBattery(3) {
			return false
		}
		state.Wear += wear
		flow.WearDelta = wear
		flow.WaterAdded = min(yield, in.Capacities.Water-state.Water)
		state.Water += flow.WaterAdded
		fatigueDelta = 2
	case "electrolyze":
		if state.Battery < 3 || state.Water < 2 {
			return false
		}
		_ = spendBattery(3)
		state.Water -= 2
		flow.WaterSpent = 2
		flow.OxygenAdded = min(6, in.Capacities.Oxygen-state.Oxygen)
		state.Oxygen += flow.OxygenAdded
		fatigueDelta = 1
	case "service":
		if state.Wear <= 0 || !spendBattery(2) {
			return false
		}
		removed := min(3, state.Wear)
		state.Wear -= removed
		flow.WearDelta = -removed
		fatigueDelta = 1
	case "patch":
		if state.Hull >= in.Capacities.Hull || !spendBattery(3) {
			return false
		}
		flow.HullAdded = min(3, in.Capacities.Hull-state.Hull)
		state.Hull += flow.HullAdded
		fatigueDelta = 2
	case "brace":
		if !spendBattery(1) {
			return false
		}
		fatigueDelta = 1
	case "research":
		if state.Battery < 2 || state.Water < 1 {
			return false
		}
		_ = spendBattery(2)
		state.Water--
		flow.WaterSpent = 1
		state.Insight += 3
		flow.InsightAdded = 3
		fatigueDelta = 1
	default:
		return false
	}
	old := state.Fatigue
	state.Fatigue = max(0, state.Fatigue+fatigueDelta)
	flow.FatigueDelta = state.Fatigue - old
	return true
}

func applyHazard(in Input, state *State, hazard string, braced bool, flow *HazardFlow) bool {
	switch hazard {
	case "none":
		return true
	case "flare":
		amount := 3
		if braced {
			amount = 1
		}
		if state.Oxygen < amount {
			return false
		}
		state.Oxygen -= amount
		flow.OxygenSpent = amount
		if !braced {
			flow.MoraleLost = min(2, state.Morale)
			state.Morale -= flow.MoraleLost
		}
	case "impact":
		amount := 4
		if braced {
			amount = 1
		}
		flow.HullLost = min(amount, state.Hull)
		state.Hull -= flow.HullLost
	case "quake":
		amount := 2
		if braced {
			amount = 1
		}
		flow.HullLost = min(amount, state.Hull)
		state.Hull -= flow.HullLost
		if !braced {
			state.Wear += 2
			flow.WearAdded = 2
		}
	}
	return state.Hull > 0 && state.Morale > 0 && state.Wear <= in.Capacities.Wear
}

func applyRation(in Input, state *State, ration string, flow *RationFlow) bool {
	pop := in.Population
	moraleNominal := 0
	switch ration {
	case "full":
		flow.OxygenSpent = 2 * pop
		flow.WaterSpent = 2 * pop
		moraleNominal = 2
	case "conserve":
		flow.OxygenSpent = pop
		flow.WaterSpent = pop
		moraleNominal = -1
		flow.FatigueAdded = 1
	case "emergency":
		if !in.AllowEmergency {
			return false
		}
		flow.OxygenSpent = pop
		flow.WaterSpent = (pop + 1) / 2
		moraleNominal = -3
		flow.FatigueAdded = 2
	default:
		return false
	}
	if state.Oxygen < flow.OxygenSpent {
		return false
	}
	state.Oxygen -= flow.OxygenSpent
	if state.Water < flow.WaterSpent {
		return false
	}
	state.Water -= flow.WaterSpent
	oldMorale := state.Morale
	state.Morale = max(0, min(in.Capacities.Morale, state.Morale+moraleNominal))
	flow.MoraleDelta = state.Morale - oldMorale
	state.Fatigue += flow.FatigueAdded
	return state.Morale > 0
}

func applyRecycler(in Input, state *State, flow *RecycleFlow) {
	amount := in.Population / 2
	switch in.Recycler {
	case "oxygen":
		flow.Added = min(amount, in.Capacities.Oxygen-state.Oxygen)
		flow.Spill = amount - flow.Added
		state.Oxygen += flow.Added
	case "water":
		flow.Added = min(amount, in.Capacities.Water-state.Water)
		flow.Spill = amount - flow.Added
		state.Water += flow.Added
	}
}

func validEnd(in Input, state State) bool {
	return state.Battery >= 0 && state.Battery <= in.Capacities.Battery && state.Oxygen > 0 && state.Oxygen <= in.Capacities.Oxygen && state.Water > 0 && state.Water <= in.Capacities.Water && state.Morale > 0 && state.Morale <= in.Capacities.Morale && state.Dust >= 0 && state.Hull > 0 && state.Hull <= in.Capacities.Hull && state.Wear >= 0 && state.Wear <= in.Capacities.Wear && state.Insight >= 0 && state.Fatigue >= 0 && state.Fatigue <= in.Capacities.Fatigue
}

func hazardResult(hazard string, braced bool) string {
	if hazard == "none" {
		return "none"
	}
	prefix := "open_"
	if braced {
		prefix = "braced_"
	}
	return prefix + hazard
}

func min(values ...int) int {
	result := values[0]
	for _, value := range values[1:] {
		if value < result {
			result = value
		}
	}
	return result
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min4(a, b, c, d int) int {
	return min(a, b, c, d)
}
