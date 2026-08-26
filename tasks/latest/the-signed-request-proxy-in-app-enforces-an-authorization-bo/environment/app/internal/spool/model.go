package spool

import (
	"time"

	"sigproxy/internal/semantics"
)

const SchemaVersion = 1

type RecordState string

const (
	StatePending   RecordState = "pending"
	StateCompleted RecordState = "completed"
	StateQuarantine RecordState = "quarantine"
)

type Record struct {
	SchemaVersion    int                 `json:"schema_version"`
	RecordID         string              `json:"record_id"`
	Sequence         int64               `json:"sequence"`
	CreatedAt        string              `json:"created_at"`
	State            RecordState         `json:"state"`
	ReplayCount      int                 `json:"replay_count"`
	WireDigest       string              `json:"wire_digest"`
	RawWirePath      string              `json:"raw_wire_path"`
	BodyPath         string              `json:"body_path"`
	SemanticRequest  *semantics.Request  `json:"semantic_request"`
	SignatureHeader  string              `json:"signature_header"`
	DecisionDigest   string              `json:"decision_digest"`
	Seal             string              `json:"seal"`
}

func NewRecord(id string, seq int64, wireDigest string, sem *semantics.Request, sigHeader, decisionDigest string) *Record {
	return &Record{
		SchemaVersion:   SchemaVersion,
		RecordID:        id,
		Sequence:        seq,
		CreatedAt:       time.Now().UTC().Format(time.RFC3339Nano),
		State:           StatePending,
		ReplayCount:     0,
		WireDigest:      wireDigest,
		SemanticRequest: sem.Clone(),
		SignatureHeader: sigHeader,
		DecisionDigest:  decisionDigest,
	}
}
