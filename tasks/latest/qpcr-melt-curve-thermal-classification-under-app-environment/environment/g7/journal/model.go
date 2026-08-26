package journal

type Event struct {
	EventID       string
	AssayID       string
	Seq           uint64
	Kind          string
	Revision      uint64
	MeasuredTm    float64
	UplinkTm      float64
	InstrumentRun string
	TargetEventID string
	ThroughSeq    uint64
	Digest        string
	Canonical     string
	Occurrences   int
}

type Policy struct {
	Schema              string   `json:"schema"`
	NonstressToleranceC float64  `json:"nonstress_tolerance_c"`
	StressAssays        []string `json:"stress_assays"`
}

type Observation struct {
	EventID       string
	AssayID       string
	Seq           uint64
	Revision      uint64
	MeasuredTm    float64
	UplinkTm      float64
	InstrumentRun string
}

type TraceRow struct {
	EventID     string `json:"event_id"`
	AssayID     string `json:"assay_id"`
	Seq         uint64 `json:"seq"`
	Kind        string `json:"kind"`
	EventDigest string `json:"event_digest"`
	Occurrences int    `json:"occurrences"`
	Effect      string `json:"effect"`
}

type AssayRow struct {
	AssayID       string  `json:"assay_id"`
	ActiveEventID string  `json:"active_event_id"`
	Revision      uint64  `json:"revision"`
	InstrumentRun string  `json:"instrument_run"`
	MeasuredTm    float64 `json:"measured_tm"`
	UplinkTm      float64 `json:"uplink_tm"`
	DeltaC        float64 `json:"delta_c"`
	ToleranceC    float64 `json:"tolerance_c"`
	Policy        string  `json:"policy"`
	Classification string `json:"classification"`
	Witness       string  `json:"witness"`
}

type Provenance struct {
	JournalDigest  string `json:"journal_digest"`
	ConfigDigest   string `json:"config_digest"`
	CacheKey       string `json:"cache_key"`
	LogicalEvents  int    `json:"logical_events"`
	DuplicateEvents int   `json:"duplicate_events"`
}

type Summary struct {
	AssaysTotal  int `json:"assays_total"`
	WithinTotal  int `json:"within_total"`
	OverTotal    int `json:"over_total"`
	OutsideTotal int `json:"outside_total"`
	TraceTotal   int `json:"trace_total"`
}

type Package struct {
	Schema     string     `json:"schema"`
	Provenance Provenance `json:"provenance"`
	Assays     []AssayRow `json:"assays"`
	Trace      []TraceRow `json:"trace"`
	Summary    Summary    `json:"summary"`
}
