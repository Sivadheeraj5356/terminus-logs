package cargograph

type DeclaredDep struct {
	Crate           string   `json:"crate"`
	Version         string   `json:"version"`
	Features        []string `json:"features"`
	DefaultFeatures bool     `json:"default_features"`
	Optional        bool     `json:"optional"`
}

type Edge struct {
	Parent           string   `json:"parent"`
	Child            string   `json:"child"`
	Version          string   `json:"version"`
	FeaturesRequested []string `json:"features_requested"`
	DefaultFeatures  bool     `json:"default_features"`
	Optional         bool     `json:"optional"`
	EdgeID           string   `json:"edge_id"`
	TargetTriple     string   `json:"target_triple"`
	DefaultCrateFeatures []string `json:"default_crate_features"`
}

type FeatureTags struct {
	DevOnlyFeatures []string `json:"dev_only_features"`
}

type Scenario struct {
	ScenarioID        string                 `json:"scenario_id"`
	BuildProfile        string                 `json:"build_profile"`
	ProfileMode         string                 `json:"profile_mode"`
	Declared            []DeclaredDep          `json:"declared"`
	WorkspacePins       map[string]string      `json:"workspace_pins"`
	WorkspaceFeatures   map[string][]string    `json:"workspace_features"`
	FeatureTags         map[string]FeatureTags `json:"feature_tags"`
	FeatureAliases      map[string][]string    `json:"feature_aliases"`
	Edges               []Edge                 `json:"edges"`
	Exclusions          []string               `json:"exclusions"`
	TraversalDepthCap   int                    `json:"traversal_depth_cap"`
	WorkspaceMembers    []string               `json:"workspace_members"`
}

type ResolvedCrate struct {
	CrateKey        string   `json:"crate_key"`
	Crate           string   `json:"crate"`
	Version         string   `json:"version"`
	Depth           int      `json:"depth"`
	Source          string   `json:"source"`
	ActiveFeatures  []string `json:"active_features"`
}

type FeatureConflict struct {
	Crate            string   `json:"crate"`
	SelectedVersion  string   `json:"selected_version"`
	RejectedVersions []string `json:"rejected_versions"`
	ResolutionReason string   `json:"resolution_reason"`
	Severity         string   `json:"severity"`
}

type ScenarioOut struct {
	ScenarioID              string            `json:"scenario_id"`
	Status                  string            `json:"status"`
	DuplicateEdgesSkipped   int               `json:"duplicate_edges_skipped"`
	FramesRejected          int               `json:"frames_rejected"`
	TruncatedTail           int               `json:"truncated_tail"`
	EdgesTraversed          int               `json:"edges_traversed"`
	ConflictRejectionCount  int               `json:"conflict_rejection_count"`
	ConflictRowsPurged      int               `json:"conflict_rows_purged"`
	ScenarioPayloadDigest   string            `json:"scenario_payload_digest"`
	ScenarioPayloadCRC32    string            `json:"scenario_payload_crc32"`
	ScenarioPayloadLen      int               `json:"scenario_payload_len"`
	ScenarioPayloadPlus     int               `json:"scenario_payload_plus"`
	PartialFeatureLiterals  int               `json:"partial_feature_literals"`
	WireReserved            int               `json:"wire_reserved"`
	ResolvedCrates          []ResolvedCrate   `json:"resolved_crates"`
	RuntimeFeatureSet       []string          `json:"runtime_feature_set"`
	FeatureConflicts        []FeatureConflict `json:"feature_conflicts"`
}

type Report struct {
	FormatVersion        int           `json:"format_version"`
	CaptureDigest        string        `json:"capture_digest"`
	CaptureChainTail     string        `json:"capture_chain_tail"`
	ManifestPayloadLen   int           `json:"manifest_payload_len"`
	ManifestPayloadLenLE string        `json:"manifest_payload_len_le"`
	BundledPayloadLen    int           `json:"bundled_payload_len"`
	BundledPayloadLenLE  string        `json:"bundled_payload_len_le"`
	Scenarios            []ScenarioOut `json:"scenarios"`
}
