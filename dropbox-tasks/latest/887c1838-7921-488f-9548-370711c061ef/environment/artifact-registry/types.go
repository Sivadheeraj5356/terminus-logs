package registry

type Summary struct {
	SessionsAnalyzed      int `json:"sessions_analyzed"`
	EquivalentSessions    int `json:"equivalent_sessions"`
	DivergentSessions     int `json:"divergent_sessions"`
	TotalDivergencesFound int `json:"total_divergences_found"`
	StressSchedulesRun    int `json:"stress_schedules_run"`
	StressSchedulesPassed int `json:"stress_schedules_passed"`
}

type Divergence struct {
	Kind      string `json:"kind"`
	Toolchain string `json:"toolchain"`
	Seq       int    `json:"seq"`
	Detail    string `json:"detail"`
}

type StressResult struct {
	SchedulesRun    int  `json:"schedules_run"`
	SchedulesPassed int  `json:"schedules_passed"`
	Validated       bool `json:"validated"`
}

type SessionResult struct {
	SessionID             string       `json:"session_id"`
	Equivalent            bool         `json:"equivalent"`
	Divergences           []Divergence `json:"divergences"`
	CheckpointValid       bool         `json:"checkpoint_valid"`
	Deterministic         bool         `json:"deterministic"`
	RollbackValid         bool         `json:"rollback_valid"`
	DistributedConsistent bool         `json:"distributed_consistent"`
	CompressionValid      bool         `json:"compression_valid"`
	SymbolConsistent      bool         `json:"symbol_consistent"`
	OptimizationDivergent bool         `json:"optimization_divergent"`
	ToolchainFixOrder     []string     `json:"toolchain_fix_order"`
	Stress                StressResult `json:"stress"`
}

type Report struct {
	Summary  Summary         `json:"summary"`
	Sessions []SessionResult `json:"sessions"`
}
