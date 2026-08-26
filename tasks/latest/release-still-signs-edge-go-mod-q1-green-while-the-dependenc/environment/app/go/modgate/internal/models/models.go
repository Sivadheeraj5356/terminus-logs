package models

type Manifest struct {
	ModuleBatchID      string `json:"module_batch_id"`
	SnapshotPack       string `json:"snapshot_pack"`
	PolicyTrack        string `json:"policy_track"`
	PinCount           int    `json:"pin_count"`
	ToolchainDeclared  string `json:"toolchain_declared"`
	ProxyAPIBase       string `json:"proxy_api_base"`
	SumdbAPIBase       string `json:"sumdb_api_base"`
	ModuleLockPath     string `json:"module_lock_path"`
	SnapshotPath       string `json:"snapshot_path"`
	ConflictReportPath string `json:"conflict_report_path"`
	ExcludeOverlayPath string `json:"exclude_overlay_path"`
	CorpusAnnexPath    string `json:"corpus_annex_path"`
	RetractmatchBin    string `json:"retractmatch_bin"`
	GofloorBin         string `json:"gofloor_bin"`
}

type Pin struct {
	ModID        string `json:"mod_id"`
	ModulePath   string `json:"module_path"`
	Version      string `json:"version"`
	Member       string `json:"member"`
	Linkage      string `json:"linkage"`
	GoFloor      string `json:"go_floor"`
	DeclaredHash string `json:"declared_hash"`
}

type SnapshotEntry struct {
	Retracted   bool   `json:"retracted"`
	ZipHash     string `json:"zip_hash"`
	BlockReason string `json:"block_reason"`
}

type ConflictPred struct {
	RefreshRetract bool
	RefreshSum     bool
}

type IntegrityRow struct {
	ModID              string `json:"mod_id"`
	ModulePath         string `json:"module_path"`
	Version            string `json:"version"`
	Member             string `json:"member"`
	Linkage            string `json:"linkage"`
	Retracted          bool   `json:"retracted"`
	ChecksumOK         bool   `json:"checksum_ok"`
	GoFloorOK          bool   `json:"go_floor_ok"`
	Excluded           bool   `json:"excluded"`
	EffectiveViolation bool   `json:"effective_violation"`
	GateAction         string `json:"gate_action"`
	PolicyBasis        string `json:"policy_basis"`
	ResolveSource      string `json:"resolve_source"`
	BlockReason        string `json:"block_reason"`
	DeclaredHash       string `json:"declared_hash"`
	LiveHash           string `json:"live_hash"`
	RefreshRetract     bool   `json:"refresh_retract"`
	RefreshSum         bool   `json:"refresh_sum"`
}

type Resolution struct {
	ModID         string `json:"mod_id"`
	PolicyBasis   string `json:"policy_basis"`
	ResolveSource string `json:"resolve_source"`
	GateAction    string `json:"gate_action"`
}

type MemberRollup struct {
	Member     string `json:"member"`
	PinCount   int    `json:"pin_count"`
	GateStatus string `json:"gate_status"`
}

type Certificate struct {
	Status            string         `json:"status"`
	ModuleBatchID     string         `json:"module_batch_id"`
	PolicyTrack       string         `json:"policy_track"`
	ToolchainDeclared string         `json:"toolchain_declared"`
	GateStatus        string         `json:"gate_status"`
	RecordCount       int            `json:"record_count"`
	LiveRefreshes     int            `json:"live_refreshes"`
	WaiverHits        int            `json:"waiver_hits"`
	StaleOverrides    int            `json:"stale_overrides"`
	RetractHits       int            `json:"retract_hits"`
	ChecksumFailures  int            `json:"checksum_failures"`
	ToolchainBlocks   int            `json:"toolchain_blocks"`
	ExcludeSkips      int            `json:"exclude_skips"`
	TransitiveWarns   int            `json:"transitive_warns"`
	ChainDigest       string         `json:"chain_digest"`
	ExportDigest      string         `json:"export_digest"`
	MemberRollups     []MemberRollup `json:"member_rollups"`
	Resolutions       []Resolution   `json:"resolutions"`
}

type PinDigest struct {
	ModID     string `json:"mod_id"`
	RowDigest string `json:"row_digest"`
}

type ReproExport struct {
	ModuleBatchID string      `json:"module_batch_id"`
	ExportDigest  string      `json:"export_digest"`
	PinDigests    []PinDigest `json:"pin_digests"`
}

type Probe struct {
	Retracted  bool
	LiveHash   string
	ChecksumOK bool
	GoFloorOK  bool
}
