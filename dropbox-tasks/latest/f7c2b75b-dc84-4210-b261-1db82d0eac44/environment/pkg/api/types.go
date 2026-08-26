package api

type GateTiming struct {
	Phase           string `json:"phase"`
	CompletedAtTick uint64 `json:"completed_at_tick"`
}

type EpochPair struct {
	ForwardEpoch           uint64 `json:"forward_epoch"`
	JournalHeadGeneration  uint64 `json:"journal_head_generation"`
}

type CycleRecord struct {
	CycleID     string       `json:"cycle_id"`
	GateTimings []GateTiming `json:"gate_timings"`
	EpochPairs  []EpochPair  `json:"epoch_pairs"`
}

type SurfaceMeasure struct {
	Name           string `json:"name"`
	Epoch          uint64 `json:"epoch"`
	LastEventTick  uint64 `json:"last_event_tick"`
}

type CycleReport struct {
	Cycles       []CycleRecord    `json:"cycles"`
	Surfaces     []SurfaceMeasure `json:"surfaces"`
	RecordDigest string           `json:"record_digest"`
}

type PhaseToken struct {
	Tick uint64
}
