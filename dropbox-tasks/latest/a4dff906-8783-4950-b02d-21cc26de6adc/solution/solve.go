package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
)

type Sailing struct {
	SailingID            string   `json:"sailing_id"`
	RouteID              string   `json:"route_id"`
	VesselClass          string   `json:"vessel_class"`
	RequiredCrewClass    string   `json:"required_crew_class"`
	Passengers           float64  `json:"passengers"`
	DisruptionMinutes    float64  `json:"disruption_minutes"`
	PriorityWeight       float64  `json:"priority_weight"`
	ServiceMinutes       float64  `json:"service_minutes"`
	EarliestWindow       int      `json:"earliest_window"`
	DeadlineWindow       int      `json:"deadline_window"`
	Mandatory            bool     `json:"mandatory"`
	PreferredHandoffMode string   `json:"preferred_handoff_mode"`
	RestRisk             float64  `json:"rest_risk"`
	TideGroup            string   `json:"tide_group"`
	AllowedTerminalZones []string `json:"allowed_terminal_zones"`
}

type Crew struct {
	CrewID               string             `json:"crew_id"`
	BaseID               string             `json:"base_id"`
	CertificationClass   string             `json:"certification_class"`
	QualifiedRoutes      []string           `json:"qualified_routes"`
	VesselClasses        []string           `json:"vessel_classes"`
	AvailableWindows     []int              `json:"available_windows"`
	ShiftRemainingMinutes float64           `json:"shift_remaining_minutes"`
	MaxSailingsPerWindow int                `json:"max_sailings_per_window"`
	RouteSkill           map[string]float64 `json:"route_skill"`
	VesselSkill          map[string]float64 `json:"vessel_skill"`
}

type Terminal struct {
	ReliefTerminalID string   `json:"relief_terminal_id"`
	ZoneID           string   `json:"zone_id"`
	Routes           []string `json:"routes"`
	VesselClasses    []string `json:"vessel_classes"`
	OpenWindows      []int    `json:"open_windows"`
	AcceptedBases    []string `json:"accepted_bases"`
	WindowCapacity   int      `json:"window_capacity"`
}

type Window struct {
	Window         int     `json:"window"`
	CrewMinutesCap float64 `json:"crew_minutes_cap"`
	TerminalSlots  int     `json:"terminal_slots"`
	TideFactor     float64 `json:"tide_factor"`
}

type WindowFile struct {
	Windows []Window `json:"windows"`
}

type CapacityFile struct {
	ByWindow map[string]map[string]int `json:"by_window"`
}

type RouteTargetFile struct {
	Routes map[string]struct {
		TargetShare        float64 `json:"target_share"`
		MinAssigned        int     `json:"min_assigned"`
		PriorityMultiplier float64 `json:"priority_multiplier"`
	} `json:"routes"`
}

type Edge struct {
	Parent string `json:"parent"`
	Child  string `json:"child"`
}

type PlanRow struct {
	SailingID          string  `json:"sailing_id"`
	CrewID             string  `json:"crew_id"`
	ReliefTerminalID   string  `json:"relief_terminal_id"`
	RecoveryWindow     int     `json:"recovery_window"`
	PriorityRank       int     `json:"priority_rank"`
	HandoffMode        string  `json:"handoff_mode"`
	RestBufferMinutes  float64 `json:"rest_buffer_minutes"`
}

type Candidate struct {
	SailingIndex  int
	CrewIndex     int
	TerminalIndex int
	Window        int
	RestBuffer    float64
	Score         float64
}

var classRank = map[string]int{"C": 1, "B": 2, "A": 3}

func readJSONL[T any](path string) ([]T, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 1024), 1024*1024)
	var rows []T
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var row T
		if err := json.Unmarshal(line, &row); err != nil {
			return nil, err
		}
		rows = append(rows, row)
	}
	return rows, scanner.Err()
}

func readJSON[T any](path string, out *T) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, out)
}

func containsString(items []string, value string) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}

func containsInt(items []int, value int) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}

func impact(s Sailing, routeMultiplier float64) float64 {
	return s.Passengers * s.DisruptionMinutes * s.PriorityWeight * routeMultiplier * (1.0 + 0.28*s.RestRisk)
}

func modeFor(s Sailing, index int) string {
	modes := []string{"RELIEF", "SWAP", "DEADHEAD", "STANDBY"}
	if s.PreferredHandoffMode != "" {
		if index%5 != 0 {
			return s.PreferredHandoffMode
		}
	}
	return modes[index%len(modes)]
}

func compatible(s Sailing, c Crew, t Terminal, window int) bool {
	if window < s.EarliestWindow || window > s.DeadlineWindow {
		return false
	}
	if !containsInt(c.AvailableWindows, window) {
		return false
	}
	if classRank[c.CertificationClass] < classRank[s.RequiredCrewClass] {
		return false
	}
	if !containsString(c.QualifiedRoutes, s.RouteID) || !containsString(c.VesselClasses, s.VesselClass) {
		return false
	}
	if !containsString(t.Routes, s.RouteID) || !containsString(t.VesselClasses, s.VesselClass) {
		return false
	}
	if !containsInt(t.OpenWindows, window) || !containsString(t.AcceptedBases, c.BaseID) {
		return false
	}
	if !containsString(s.AllowedTerminalZones, t.ZoneID) {
		return false
	}
	return true
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: ferry_solver <input_dir> <output_dir>")
		os.Exit(2)
	}
	inputDir := os.Args[1]
	outputDir := os.Args[2]
	sailings, err := readJSONL[Sailing](filepath.Join(inputDir, "sailings.jsonl"))
	if err != nil {
		panic(err)
	}
	crews, err := readJSONL[Crew](filepath.Join(inputDir, "crews.jsonl"))
	if err != nil {
		panic(err)
	}
	terminals, err := readJSONL[Terminal](filepath.Join(inputDir, "relief_terminals.jsonl"))
	if err != nil {
		panic(err)
	}
	var routeTargets RouteTargetFile
	if err := readJSON(filepath.Join(inputDir, "route_targets.json"), &routeTargets); err != nil {
		panic(err)
	}
	var capacity CapacityFile
	if err := readJSON(filepath.Join(inputDir, "vessel_capacity.json"), &capacity); err != nil {
		panic(err)
	}
	edges, err := readJSONL[Edge](filepath.Join(inputDir, "precedence_edges.jsonl"))
	if err != nil {
		panic(err)
	}

	routeMult := make(map[string]float64)
	for route, target := range routeTargets.Routes {
		routeMult[route] = target.PriorityMultiplier
	}
	childrenByParent := map[string][]string{}
	parentByChild := map[string][]string{}
	for _, edge := range edges {
		childrenByParent[edge.Parent] = append(childrenByParent[edge.Parent], edge.Child)
		parentByChild[edge.Child] = append(parentByChild[edge.Child], edge.Parent)
	}

	sort.Slice(sailings, func(i, j int) bool {
		left := impact(sailings[i], routeMult[sailings[i].RouteID])
		right := impact(sailings[j], routeMult[sailings[j].RouteID])
		if sailings[i].Mandatory != sailings[j].Mandatory {
			return sailings[i].Mandatory
		}
		if math.Abs(left-right) > 0.001 {
			return left > right
		}
		return sailings[i].SailingID < sailings[j].SailingID
	})
	indexByID := map[string]int{}
	for idx, sailing := range sailings {
		indexByID[sailing.SailingID] = idx
	}

	assigned := map[string]PlanRow{}
	crewMinutes := map[string]float64{}
	crewWindow := map[string]int{}
	terminalWindow := map[string]int{}
	vesselWindow := map[string]int{}
	windowCount := map[int]int{}
	routeCount := map[string]int{}
	baseCount := map[string]int{}
	modeCount := map[string]int{}
	cellCount := map[string]int{}

	tryAssign := func(idx int, forceCellBase string, forceWindow int) bool {
		s := sailings[idx]
		if _, ok := assigned[s.SailingID]; ok {
			return true
		}
		minParentWindow := 0
		for _, parent := range parentByChild[s.SailingID] {
			parentRow, ok := assigned[parent]
			if !ok {
				return false
			}
			if parentRow.RecoveryWindow > minParentWindow {
				minParentWindow = parentRow.RecoveryWindow
			}
		}
		var candidates []Candidate
		for ci, crew := range crews {
			for ti, terminal := range terminals {
				for window := s.EarliestWindow; window <= s.DeadlineWindow; window++ {
					if forceWindow != 0 && window != forceWindow {
						continue
					}
					if window < minParentWindow {
						continue
					}
					if windowCount[window] >= 35 {
						continue
					}
					if forceCellBase != "" && crew.BaseID != forceCellBase {
						continue
					}
					if !compatible(s, crew, terminal, window) {
						continue
					}
					buffer := math.Round(10 + 70*s.RestRisk + float64((idx+window+ci)%9-4))
					if buffer < 10 {
						buffer = 10
					}
					if buffer > 90 {
						buffer = 90
					}
					if crewMinutes[crew.CrewID]+s.ServiceMinutes+buffer*0.24 > crew.ShiftRemainingMinutes {
						continue
					}
					cwKey := fmt.Sprintf("%s|%d", crew.CrewID, window)
					if crewWindow[cwKey] >= crew.MaxSailingsPerWindow {
						continue
					}
					twKey := fmt.Sprintf("%s|%d", terminal.ReliefTerminalID, window)
					if terminalWindow[twKey] >= terminal.WindowCapacity {
						continue
					}
					vwKey := fmt.Sprintf("%d|%s", window, s.VesselClass)
					if vesselWindow[vwKey] >= capacity.ByWindow[fmt.Sprintf("%d", window)][s.VesselClass] {
						continue
					}
					cellKey := fmt.Sprintf("%d|%s", window, crew.BaseID)
					score := impact(s, routeMult[s.RouteID])
					score += crew.RouteSkill[s.RouteID] * 9000
					score += crew.VesselSkill[s.VesselClass] * 8000
					score -= float64(window-s.EarliestWindow) * 2200
					score -= float64(windowCount[window]) * 1100
					score -= float64(routeCount[s.RouteID]) * 720
					score -= float64(baseCount[crew.BaseID]) * 680
					score -= float64(terminalWindow[twKey]) * 520
					if cellCount[cellKey] == 0 {
						score += 180000
					}
					if s.Mandatory {
						score += 220000
					}
					candidates = append(candidates, Candidate{idx, ci, ti, window, buffer, score})
				}
			}
		}
		if len(candidates) == 0 {
			return false
		}
		sort.Slice(candidates, func(i, j int) bool {
			if math.Abs(candidates[i].Score-candidates[j].Score) > 0.001 {
				return candidates[i].Score > candidates[j].Score
			}
			return crews[candidates[i].CrewIndex].CrewID < crews[candidates[j].CrewIndex].CrewID
		})
		best := candidates[0]
		crew := crews[best.CrewIndex]
		terminal := terminals[best.TerminalIndex]
		mode := modeFor(s, len(assigned)+idx)
		row := PlanRow{
			SailingID:         s.SailingID,
			CrewID:            crew.CrewID,
			ReliefTerminalID:  terminal.ReliefTerminalID,
			RecoveryWindow:    best.Window,
			PriorityRank:      0,
			HandoffMode:       mode,
			RestBufferMinutes: best.RestBuffer,
		}
		assigned[s.SailingID] = row
		crewMinutes[crew.CrewID] += s.ServiceMinutes + best.RestBuffer*0.24
		crewWindow[fmt.Sprintf("%s|%d", crew.CrewID, best.Window)]++
		terminalWindow[fmt.Sprintf("%s|%d", terminal.ReliefTerminalID, best.Window)]++
		vesselWindow[fmt.Sprintf("%d|%s", best.Window, s.VesselClass)]++
		windowCount[best.Window]++
		routeCount[s.RouteID]++
		baseCount[crew.BaseID]++
		modeCount[mode]++
		cellCount[fmt.Sprintf("%d|%s", best.Window, crew.BaseID)]++
		return true
	}

	bases := []string{"BAY", "CENTRAL", "ISLAND", "YARD"}
	for window := 1; window <= 6; window++ {
		for _, base := range bases {
			for idx := range sailings {
				if tryAssign(idx, base, window) {
					break
				}
			}
		}
	}

	for _, sailing := range sailings {
		if !sailing.Mandatory {
			continue
		}
		for _, parent := range parentByChild[sailing.SailingID] {
			if parentIdx, ok := indexByID[parent]; ok {
				tryAssign(parentIdx, "", 0)
			}
		}
		if !tryAssign(indexByID[sailing.SailingID], "", 0) {
			fmt.Fprintf(os.Stderr, "failed to assign mandatory sailing %s\n", sailing.SailingID)
			os.Exit(1)
		}
	}

	for len(assigned) < 160 {
		progress := false
		for idx := range sailings {
			if len(assigned) >= 160 {
				break
			}
			if _, ok := assigned[sailings[idx].SailingID]; ok {
				continue
			}
			for _, parent := range parentByChild[sailings[idx].SailingID] {
				if parentIdx, ok := indexByID[parent]; ok {
					tryAssign(parentIdx, "", 0)
				}
			}
			if tryAssign(idx, "", 0) {
				progress = true
			}
		}
		if !progress {
			break
		}
	}

	var rows []PlanRow
	for _, row := range assigned {
		rows = append(rows, row)
	}
	sort.Slice(rows, func(i, j int) bool {
		left := impact(findSailing(rows[i].SailingID, sailings), routeMult[findSailing(rows[i].SailingID, sailings).RouteID])
		right := impact(findSailing(rows[j].SailingID, sailings), routeMult[findSailing(rows[j].SailingID, sailings).RouteID])
		if math.Abs(left-right) > 0.001 {
			return left > right
		}
		return rows[i].SailingID < rows[j].SailingID
	})
	for idx := range rows {
		rows[idx].PriorityRank = idx + 1
	}

	if err := os.MkdirAll(outputDir, 0755); err != nil {
		panic(err)
	}
	planPath := filepath.Join(outputDir, "ferry_recovery_plan.jsonl")
	planFile, err := os.Create(planPath)
	if err != nil {
		panic(err)
	}
	encoder := json.NewEncoder(planFile)
	for _, row := range rows {
		if err := encoder.Encode(row); err != nil {
			panic(err)
		}
	}
	planFile.Close()

	sailingByID := map[string]Sailing{}
	crewByID := map[string]Crew{}
	for _, sailing := range sailings {
		sailingByID[sailing.SailingID] = sailing
	}
	for _, crew := range crews {
		crewByID[crew.CrewID] = crew
	}
	summaryWindow := map[string]int{}
	summaryRoute := map[string]int{}
	summaryCrew := map[string]int{}
	summaryTerminal := map[string]int{}
	protected := 0.0
	for _, row := range rows {
		sailing := sailingByID[row.SailingID]
		summaryWindow[fmt.Sprintf("%d", row.RecoveryWindow)]++
		summaryRoute[sailing.RouteID]++
		summaryCrew[row.CrewID]++
		summaryTerminal[row.ReliefTerminalID]++
		protected += sailing.Passengers * sailing.DisruptionMinutes
		_ = crewByID[row.CrewID]
	}
	summary := map[string]any{
		"assigned_count":                     len(rows),
		"window_counts":                      summaryWindow,
		"route_counts":                       summaryRoute,
		"crew_counts":                        summaryCrew,
		"terminal_counts":                    summaryTerminal,
		"total_protected_passenger_minutes": math.Round(protected*1000) / 1000,
	}
	data, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(filepath.Join(outputDir, "ferry_recovery_summary.json"), append(data, '\n'), 0644); err != nil {
		panic(err)
	}
}

func findSailing(id string, sailings []Sailing) Sailing {
	for _, sailing := range sailings {
		if sailing.SailingID == id {
			return sailing
		}
	}
	panic("missing sailing " + id)
}
