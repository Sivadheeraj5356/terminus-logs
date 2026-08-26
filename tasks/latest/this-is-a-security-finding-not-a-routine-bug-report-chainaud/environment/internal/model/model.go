// Package model holds the row-level data structures shared by the store,
// canon, merkle and audit packages.
package model

// Stream is a row from the streams table.
type Stream struct {
	StreamID           string
	MigratedAt         *int64 // nil = pure v1 legacy, never migrated
	CheckpointInterval  int64
	RetentionDays       int64
	LegalHold           bool
	CreatedAt           int64
}

// Event is a row from the events table.
type Event struct {
	StreamID  string
	Seq       int64
	Ts        int64
	EventType string
	Payload   []byte
	Tombstone bool
	LegalHold bool
	LeafHash  []byte // 32 bytes, computed at ingestion time
}

// Checkpoint is a row from the checkpoints table.
type Checkpoint struct {
	StreamID    string
	BatchIndex  int64
	StartSeq    int64
	EndSeq      int64
	MerkleRoot  []byte // 32 bytes
	Signature   []byte
	KeyID       string
	CreatedAt   int64
}
