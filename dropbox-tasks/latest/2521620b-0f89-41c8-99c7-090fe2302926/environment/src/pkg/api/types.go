package api

type EventRow struct {
	Seq    int    `json:"seq"`
	Sec    int64  `json:"sec"`
	Nsec   int64  `json:"nsec"`
	Action string `json:"action"`
}

type Segment struct {
	ID        int        `json:"id"`
	BaseSeq   int        `json:"base_seq"`
	OffsetMin int        `json:"offset_min"`
	Events    []EventRow `json:"events"`
}

type CompactStep struct {
	Left  int `json:"left"`
	Right int `json:"right"`
}

type Scenario struct {
	Name         string        `json:"name"`
	SessionEpoch int           `json:"session_epoch"`
	Segments     []Segment     `json:"segments"`
	Compact      []CompactStep `json:"compact,omitempty"`
	WitnessSalt  string        `json:"witness_salt"`
}

type Pack struct {
	Scenarios []Scenario `json:"scenarios"`
}

type ScenarioResult struct {
	Name              string `json:"name"`
	Finish            string `json:"finish"`
	ActiveSessionEpoch int    `json:"active_session_epoch"`
	EventsReplayed    int    `json:"events_replayed"`
	ChainIntact       int    `json:"chain_intact"`
	OrderDriftCount   int    `json:"order_drift_count"`
	ContradictionCount int   `json:"contradiction_count"`
	WitnessOKCount    int    `json:"witness_ok_count"`
	TimelineHeadHex   string `json:"timeline_head_hex"`
}

type Report struct {
	SchemaVersion int              `json:"schema_version"`
	Scenarios     []ScenarioResult `json:"scenarios"`
}
