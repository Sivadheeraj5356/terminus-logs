package scenpack

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

type Meta struct {
	ScenarioID         string `json:"scenario_id"`
	RequiredClearance  string `json:"required_clearance"`
	RolloutEpoch       int    `json:"rollout_epoch"`
	TopologyRevision   string `json:"topology_revision"`
}

type Decision struct {
	ID          string         `json:"id"`
	Class       string         `json:"class"`
	DirectUnits []string       `json:"direct_units"`
	Window      Window         `json:"window"`
	Exclusive   bool           `json:"exclusive"`
	Flags       []string       `json:"flags"`
	Clearance   string         `json:"clearance,omitempty"`
}

type Window struct {
	Start int `json:"start"`
	End   int `json:"end"`
}

type DepEdge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

type Booking struct {
	Pool       string `json:"pool"`
	DecisionID string `json:"decision_id"`
	Start      int    `json:"start"`
	End        int    `json:"end"`
}

type TopoEdge struct {
	Parent string `json:"parent"`
	Child  string `json:"child"`
}

type Policy struct {
	ClassGates      map[string][]string `json:"class_gates"`
	ScoreThresholds []struct {
		MinScore   int      `json:"min_score"`
		ExtraRoles []string `json:"extra_roles"`
	} `json:"score_thresholds"`
	Conditional struct {
		ExceptionFlag string `json:"exception_flag"`
		ExtraRole     string `json:"extra_role"`
	} `json:"conditional"`
}

type Scenario struct {
	Meta        Meta
	Decisions   []Decision
	DecisionIDs []string
	UnitIDs     []string
	DepEdges    []DepEdge
	Bookings    []Booking
	TopoEdges   []TopoEdge
	Windows     map[string]Window
	Exclusive   map[string]bool
	Flags       map[string][]string
	Clearances  map[string]string
	Classes     map[string]string
}

func LoadPolicy(path string) (*Policy, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p Policy
	if err := json.Unmarshal(b, &p); err != nil {
		return nil, err
	}
	return &p, nil
}

func LoadScenario(dir string) (*Scenario, error) {
	sc := &Scenario{
		Windows:    map[string]Window{},
		Exclusive:  map[string]bool{},
		Flags:      map[string][]string{},
		Clearances: map[string]string{},
		Classes:    map[string]string{},
	}
	mb, err := os.ReadFile(filepath.Join(dir, "meta.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(mb, &sc.Meta); err != nil {
		return nil, err
	}
	f, err := os.Open(filepath.Join(dir, "decisions.jsonl"))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	s := bufio.NewScanner(f)
	for s.Scan() {
		line := s.Bytes()
		if len(line) == 0 {
			continue
		}
		var d Decision
		if err := json.Unmarshal(line, &d); err != nil {
			return nil, err
		}
		sort.Strings(d.DirectUnits)
		sort.Strings(d.Flags)
		sc.Decisions = append(sc.Decisions, d)
		sc.DecisionIDs = append(sc.DecisionIDs, d.ID)
		sc.Windows[d.ID] = d.Window
		sc.Exclusive[d.ID] = d.Exclusive
		sc.Flags[d.ID] = append([]string(nil), d.Flags...)
		sc.Clearances[d.ID] = d.Clearance
		sc.Classes[d.ID] = d.Class
	}
	if err := s.Err(); err != nil {
		return nil, err
	}
	sort.Strings(sc.DecisionIDs)

	var unitsWrap struct {
		Units []struct {
			ID string `json:"id"`
		} `json:"units"`
	}
	ub, err := os.ReadFile(filepath.Join(dir, "units.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(ub, &unitsWrap); err != nil {
		return nil, err
	}
	for _, u := range unitsWrap.Units {
		sc.UnitIDs = append(sc.UnitIDs, u.ID)
	}
	sort.Strings(sc.UnitIDs)

	var depsWrap struct {
		Edges []DepEdge `json:"edges"`
	}
	db, err := os.ReadFile(filepath.Join(dir, "dependencies.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(db, &depsWrap); err != nil {
		return nil, err
	}
	sc.DepEdges = depsWrap.Edges

	var resWrap struct {
		Bookings []Booking `json:"bookings"`
	}
	rb, err := os.ReadFile(filepath.Join(dir, "resources.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(rb, &resWrap); err != nil {
		return nil, err
	}
	sc.Bookings = resWrap.Bookings

	var topoWrap struct {
		Edges []TopoEdge `json:"edges"`
	}
	tb, err := os.ReadFile(filepath.Join(dir, "topology.json"))
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(tb, &topoWrap); err != nil {
		return nil, err
	}
	sc.TopoEdges = topoWrap.Edges
	return sc, nil
}
