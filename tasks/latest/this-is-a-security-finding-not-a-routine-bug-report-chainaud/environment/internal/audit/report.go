// Package audit computes chain state -- verification and compaction -- from
// data already loaded from the store. It is the one place both the verify
// and compact commands route through, so their view of a stream's chain_tip_hash
// can never drift apart.
package audit

type StreamVerifyReport struct {
	StreamID        string   `json:"stream_id"`
	Status          string   `json:"status"`
	EventCount      int      `json:"event_count"`
	CheckpointCount int      `json:"checkpoint_count"`
	ChainTipHash    string   `json:"chain_tip_hash"`
	FirstBadSeq     *int64   `json:"first_bad_seq"`
	FirstBadBatch   *int64   `json:"first_bad_batch"`
	Reason          *string  `json:"reason"`
	RevokedKeyIDs   []string `json:"revoked_key_ids"`
}

type VerifyReport struct {
	DBPath          string               `json:"db_path"`
	Streams         []StreamVerifyReport `json:"streams"`
	ChainTipHashAll string               `json:"chain_tip_hash_overall"`
}

type StreamCompactManifest struct {
	StreamID        string  `json:"stream_id"`
	BatchesPruned   []int64 `json:"batches_pruned"`
	BatchesRetained []int64 `json:"batches_retained"`
	EventsDeleted   int64   `json:"events_deleted"`
	ChainTipHash    string  `json:"chain_tip_hash"`
}

type CompactManifest struct {
	DBPath  string                   `json:"db_path"`
	Now     int64                    `json:"now"`
	Streams []StreamCompactManifest  `json:"streams"`
}
