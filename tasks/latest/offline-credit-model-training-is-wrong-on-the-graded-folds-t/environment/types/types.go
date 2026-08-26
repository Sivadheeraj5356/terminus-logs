package types

type FeatureRev struct {
	RevID       string             `json:"rev_id"`
	EntityID    string             `json:"entity_id"`
	ValidFromMs int64              `json:"valid_from_ms"`
	IngestedMs  int64              `json:"ingested_ms"`
	Revoked     bool               `json:"revoked"`
	Values      map[string]float64 `json:"values"`
}

type FrameOp struct {
	Op    string      `json:"op"`
	Rev   *FeatureRev `json:"rev,omitempty"`
	RevID string      `json:"rev_id,omitempty"`
}

type EventRow struct {
	EventID  string `json:"event_id"`
	EntityID string `json:"entity_id"`
	EventMs  int64  `json:"event_ms"`
}

type RemapRow struct {
	Alias        string `json:"alias"`
	Canonical    string `json:"canonical"`
	ActiveFromMs int64  `json:"active_from_ms"`
}

type FoldCfg struct {
	FoldID       string   `json:"fold_id"`
	WatermarkMs  int64    `json:"watermark_ms"`
	LagMs        int64    `json:"lag_ms"`
	EventPack    string   `json:"event_pack"`
	FeaturePacks []string `json:"feature_packs"`
	RemapPack    string   `json:"remap_pack"`
}

type PickArgs struct {
	Entity string
	TMs    int64
	WmMs   int64
	LagMs  int64
	Pool   []FeatureRev
}

type PickResult struct {
	Rev        *FeatureRev
	Candidates []string
}

type RowOut struct {
	EventID  string             `json:"event_id"`
	EntityID string             `json:"entity_id"`
	FeatRev  string             `json:"feat_rev"`
	FeatHash string             `json:"feat_hash"`
	AsofMs   int64              `json:"asof_ms"`
	Values   map[string]float64 `json:"values"`
}

type AuditEntry struct {
	EventID        string   `json:"event_id"`
	RequestEntity  string   `json:"request_entity"`
	ResolvedEntity string   `json:"resolved_entity"`
	CandidateRevs  []string `json:"candidate_revs"`
	ChosenRev      string   `json:"chosen_rev"`
	Policy         string   `json:"policy"`
}

type PitReport struct {
	FoldID       string       `json:"fold_id"`
	RowCount     int          `json:"row_count"`
	Rows         []RowOut     `json:"rows"`
	AuditTrace   []AuditEntry `json:"audit_trace"`
	LedgerDigest string       `json:"ledger_digest"`
}

type JournalEntry struct {
	FoldID       string   `json:"fold_id"`
	LedgerDigest string   `json:"ledger_digest"`
	RowCount     int      `json:"row_count"`
	SegDigests   []string `json:"seg_digests"`
}
