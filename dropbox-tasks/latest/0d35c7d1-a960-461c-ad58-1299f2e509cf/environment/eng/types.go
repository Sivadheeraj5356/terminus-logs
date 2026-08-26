package eng

import (
	"qxhub/fyn"
	"qxhub/jor"
	"qxhub/pex"
)

// FixtureFile is one arm pack under fixtures/qv/.
type FixtureFile struct {
	Arm      string         `json:"arm"`
	Phase    string         `json:"phase"`
	RowCap   int            `json:"row_cap"`
	GroupCap int            `json:"group_cap"`
	Cells    []jor.CellSpec `json:"cells"`
}

// Plan is one prepared (not yet committed) arm derivation.
type Plan struct {
	Arm      string         `json:"arm"`
	Phase    string         `json:"phase"`
	Gen      int            `json:"gen"`
	Floor    int            `json:"floor"`
	Epoch    int            `json:"epoch"`
	Token    string         `json:"token"`
	Pane     string         `json:"pane"`
	Twin     string         `json:"twin"`
	Rows     []fyn.LaneRow  `json:"rows"`
	Outs     []pex.CellOut  `json:"outs"`
	Groups   []string       `json:"groups"`
	Hops     []pex.HopRec   `json:"hops"`
	RowCap   int            `json:"row_cap"`
	GroupCap int            `json:"group_cap"`
	Cells    []jor.CellSpec `json:"cells"`
}

// Audit is the emitted route audit document.
type Audit struct {
	Arm              string        `json:"arm"`
	RuleRows         []fyn.LaneRow `json:"rule_rows"`
	RouteCount       int           `json:"route_count"`
	GroupCount       int           `json:"group_count"`
	CellOutcomes     []pex.CellOut `json:"cell_outcomes"`
	GroupKeys        []string      `json:"group_keys"`
	HopRecords       []pex.HopRec  `json:"hop_records"`
	PaneDigest       string        `json:"pane_digest"`
	TwinDigest       string        `json:"twin_digest"`
	ExpectedRowCap   int           `json:"expected_row_cap"`
	ExpectedGroupCap int           `json:"expected_group_cap"`
	SessionFloor     int           `json:"session_floor"`
	SessionGen       int           `json:"session_gen"`
	Interrupt        bool          `json:"interrupt"`
	RunStamp         string        `json:"run_stamp"`
	Generation       int           `json:"generation"`
	ManifestSeal     string        `json:"manifest_seal"`
	LedgerHead       string        `json:"ledger_head"`
	PlanToken        string        `json:"plan_token"`
	Status           string        `json:"status"`
}
