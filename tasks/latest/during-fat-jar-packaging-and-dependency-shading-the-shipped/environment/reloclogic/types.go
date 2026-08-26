package reloclogic

// Finding is one relocation consistency issue.
type Finding struct {
	Kind     string `json:"kind"`
	Subject  string `json:"subject"`
	Expected string `json:"expected"`
	Observed string `json:"observed"`
	RuleID   string `json:"rule_id"`
}

// Replay holds optional schedule replay tallies.
type Replay struct {
	SchedulesRun    int  `json:"schedules_run"`
	SchedulesPassed int  `json:"schedules_passed"`
	Stable          bool `json:"stable"`
}

// BatchResult is one analyzed batch row.
type BatchResult struct {
	BatchID       string    `json:"batch_id"`
	RelocationOK  bool      `json:"relocation_ok"`
	Findings      []Finding `json:"findings"`
	MappingOK     bool      `json:"mapping_ok"`
	RewriteOK     bool      `json:"rewrite_ok"`
	IsolationOK   bool      `json:"isolation_ok"`
	IdentityOK    bool      `json:"identity_ok"`
	RollbackOK    bool      `json:"rollback_ok"`
	Replay        Replay    `json:"replay"`
}

// Summary is the aggregate rollup.
type Summary struct {
	BatchesAnalyzed int `json:"batches_analyzed"`
	FailedBatches   int `json:"failed_batches"`
	CleanBatches    int `json:"clean_batches"`
	TotalFindings   int `json:"total_findings"`
	ReplayRuns      int `json:"replay_runs"`
	ReplayPassed    int `json:"replay_passed"`
}

// Report is the aggregate JSON document.
type Report struct {
	Summary Summary       `json:"summary"`
	Batches []BatchResult `json:"batches"`
}

// Policy is the parsed reloc-canon document.
type Policy struct {
	Ordering struct {
		PrimaryKey   string
		SecondaryKey string
	}
	ChainRelocations            bool
	CascadeNested               bool
	ForbidCrossRootMerge        bool
	RequiredRelocatorEpoch      int
	PrefixStableOnFindings      bool
	FullUnstableOnFindings      bool
	DetectShadowedMappings      bool
	CascadeGapSuppressesNested  bool
	DigestBindActiveMaps        bool
	CollisionTopLevelOnly       bool
	CheckResourceRewrites       bool
	DigestBindResources         bool
	PreserveIdentityVersion     bool
	DigestBindEffectiveMaps     bool
	ReplaySkipsDigest           bool
	DetectDanglingObservations  bool
	DigestMapBindOrderSeq       bool
	RequireExactRelocatorEpoch  bool
	OrphanRequiresPayload       bool
	DigestExcludeCycleMaps      bool
	ReplayIgnoreUnknownSeqs     bool
	DetectDanglingNested        bool
}
