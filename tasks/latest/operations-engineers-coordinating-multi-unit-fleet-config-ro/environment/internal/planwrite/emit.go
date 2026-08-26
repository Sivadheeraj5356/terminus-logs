package planwrite

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"

	"odip/internal/unitfan"
	"odip/internal/scenpack"
)

type Lattice struct {
	SchemaVersion      string                `json:"schema_version"`
	ScenarioID         string                `json:"scenario_id"`
	RolloutEpoch       int                   `json:"rollout_epoch"`
	TopologyRevision   string                `json:"topology_revision"`
	DecisionIDs        []string              `json:"decision_ids"`
	UnitIDs            []string              `json:"unit_ids"`
	DependencyEdges    []scenpack.DepEdge    `json:"dependency_edges"`
	ImpactRows         []unitfan.ImpactRow   `json:"impact_rows"`
	ResourceBookings   []scenpack.Booking    `json:"resource_bookings"`
	CycleDetected      bool                  `json:"cycle_detected"`
	CyclePath          []string              `json:"cycle_path"`
	LatticeDigest      string                `json:"lattice_digest"`
	// planning aids persisted for plan stage (documented as lattice payload)
	Decisions  []scenpack.Decision        `json:"decisions"`
	Meta       scenpack.Meta              `json:"meta"`
	Windows    map[string]scenpack.Window `json:"windows"`
	Exclusive  map[string]bool            `json:"exclusive"`
	Flags      map[string][]string        `json:"flags"`
	Clearances map[string]string          `json:"clearances"`
	Classes    map[string]string          `json:"classes"`
}

type ApprovalStep struct {
	DecisionID string   `json:"decision_id"`
	Roles      []string `json:"roles"`
}

type Conflict struct {
	Type      string `json:"type"`
	Pool      string `json:"pool,omitempty"`
	Unit      string `json:"unit,omitempty"`
	DecisionA string `json:"decision_a"`
	DecisionB string `json:"decision_b"`
}

type RegBlock struct {
	Type       string `json:"type"`
	DecisionID string `json:"decision_id"`
	Reason     string `json:"reason"`
}

type Plan struct {
	SchemaVersion      string         `json:"schema_version"`
	ScenarioID         string         `json:"scenario_id"`
	RolloutEpoch       int            `json:"rollout_epoch"`
	TopologyRevision   string         `json:"topology_revision"`
	BoundLatticeDigest string         `json:"bound_lattice_digest"`
	EpochSeal          string         `json:"epoch_seal"`
	WindowDigest       string         `json:"window_digest"`
	BookingDigest      string         `json:"booking_digest"`
	ExecutionOrder     []string       `json:"execution_order"`
	ApprovalSteps      []ApprovalStep `json:"approval_steps"`
	Conflicts          []Conflict     `json:"conflicts"`
	RegulatoryBlocks   []RegBlock     `json:"regulatory_blocks"`
	Feasible           bool           `json:"feasible"`
	CycleDetected      bool           `json:"cycle_detected"`
	CyclePath          []string       `json:"cycle_path"`
	PlanDigest         string         `json:"plan_digest"`
}

func WriteLattice(path string, lat *Lattice) error {
	b, err := json.MarshalIndent(lat, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func ReadLattice(path string) (*Lattice, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var lat Lattice
	if err := json.Unmarshal(b, &lat); err != nil {
		return nil, err
	}
	return &lat, nil
}

func WritePlan(path string, plan *Plan) error {
	b, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func LatticeDigest(lat *Lattice) string {
	clone := *lat
	clone.LatticeDigest = ""
	body, _ := canonicalJSON(clone)
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

func PlanDigest(plan *Plan) string {
	clone := *plan
	clone.PlanDigest = ""
	body, _ := canonicalJSON(clone)
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

func canonicalJSON(v any) ([]byte, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var obj any
	if err := json.Unmarshal(b, &obj); err != nil {
		return nil, err
	}
	obj = sortKeys(obj)
	return json.Marshal(obj)
}

func sortKeys(v any) any {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := make(map[string]any, len(t))
		for _, k := range keys {
			out[k] = sortKeys(t[k])
		}
		return out
	case []any:
		for i := range t {
			t[i] = sortKeys(t[i])
		}
		return t
	default:
		return v
	}
}
