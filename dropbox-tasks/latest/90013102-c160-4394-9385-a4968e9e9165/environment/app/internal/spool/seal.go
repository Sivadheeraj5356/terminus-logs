package spool

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"

	"sigproxy/internal/semantics"
)

type sealPayload struct {
	SchemaVersion   int    `json:"schema_version"`
	RecordID        string `json:"record_id"`
	Sequence        int64  `json:"sequence"`
	WireDigest      string `json:"wire_digest"`
	DecisionDigest  string `json:"decision_digest"`
	SemanticDigest  string `json:"semantic_digest"`
	SignatureHeader string `json:"signature_header"`
	State           string `json:"state"`
}

func semanticDigest(sem *semantics.Request) string {
	if sem == nil {
		return ""
	}
	s := struct {
		RequestID        string `json:"request_id"`
		ProfileID        string `json:"profile_id"`
		ProfileEpoch     int    `json:"profile_epoch"`
		CanonicalTarget  string `json:"canonical_target"`
		EntityBodySHA256 string `json:"entity_body_sha256"`
	}{
		RequestID:        sem.RequestID,
		ProfileID:        sem.ProfileID,
		ProfileEpoch:     sem.ProfileEpoch,
		CanonicalTarget:  sem.CanonicalTarget,
		EntityBodySHA256: sem.EntityBodySHA256,
	}
	b, _ := json.Marshal(s)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func ComputeSeal(record *Record, sealKey []byte) (string, error) {
	payload := sealPayload{
		SchemaVersion:   record.SchemaVersion,
		RecordID:        record.RecordID,
		Sequence:        record.Sequence,
		WireDigest:      record.WireDigest,
		DecisionDigest:  record.DecisionDigest,
		SemanticDigest:  semanticDigest(record.SemanticRequest),
		SignatureHeader: record.SignatureHeader,
		State:           string(record.State),
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	m := hmac.New(sha256.New, sealKey)
	m.Write(b)
	return hex.EncodeToString(m.Sum(nil)), nil
}

func VerifySeal(record *Record, sealKey []byte) bool {
	expected, err := ComputeSeal(record, sealKey)
	if err != nil {
		return false
	}
	return hmac.Equal([]byte(expected), []byte(record.Seal))
}
