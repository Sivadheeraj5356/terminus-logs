package checkpoint

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/terminus/hopledger/digest"
	"github.com/terminus/hopledger/state"
)

type AuditCounts struct {
	CancelledEvents    int `json:"cancelled_events"`
	SupersededEvents   int `json:"superseded_events"`
	DuplicateRawEvents int `json:"duplicate_raw_events"`
	SuppressedHops     int `json:"suppressed_hops"`
}

type Snapshot struct {
	SchemaVersion       int                         `json:"schema_version"`
	Epoch               int                         `json:"epoch"`
	NextSeq             int                         `json:"next_seq"`
	AppliedEvents       int                         `json:"applied_events"`
	AuditCounts         AuditCounts                 `json:"audit_counts"`
	PolicyState         interface{}                 `json:"policy_state"`
	PolicyUpdates       []map[string]interface{}    `json:"policy_updates"`
	PolicyLineageDigest string                      `json:"policy_lineage_digest"`
	Links               map[string]state.Link       `json:"links"`
	WinnerKeys          [][]interface{}             `json:"winner_keys"`
	LineCursors         map[string]int              `json:"line_cursors"`
	RawInputDigest      string                      `json:"raw_input_digest"`
}

func Load(dir, tag string) (*Snapshot, error) {
	path := filepath.Join(dir, tag+".snap")
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var snap Snapshot
	if err := json.Unmarshal(raw, &snap); err != nil {
		return nil, err
	}
	return &snap, nil
}

func Write(dir, tag string, snap Snapshot) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	canon, err := digest.CanonicalizeStruct(snap)
	if err != nil {
		return err
	}
	raw := digest.CanonicalJSON(canon) + "\n"
	path := filepath.Join(dir, tag+".snap")
	return os.WriteFile(path, []byte(raw), 0o644)
}
