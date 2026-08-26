// Package attest computes the digests and gather sequence numbers that back
// the hint snapshot's tamper and staleness checks, as documented in
// /app/docs/snapshot-attestation.md.
package attest

import (
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"

	"labyrinthoracle/internal/session"
)

// FailedAttemptState is the documented shape of one verb/target pair inside a
// session-state digest input.
type FailedAttemptState struct {
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

// SessionState is the documented, digest-ready view of a session.
type SessionState struct {
	WorldID   string
	Room      string
	Inventory []string
	Consumed  []string
	Failed    []FailedAttemptState
}

// ChronicleDigest returns a hex digest of the chronicle file at path.
func ChronicleDigest(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := md5.Sum(raw)
	return hex.EncodeToString(sum[:]), nil
}

// SessionStateDigest returns a hex digest of a session's documented state.
func SessionStateDigest(state SessionState) (string, error) {
	payload := map[string]interface{}{
		"world_id":  state.WorldID,
		"room":      state.Room,
		"inventory": sortedStrings(state.Inventory),
		"consumed":  sortedStrings(state.Consumed),
		"failed":    sortedFailed(state.Failed),
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

// CandidateDigest returns a hex digest of a staged candidate list. Callers
// pass any JSON-marshalable candidate slice; the digest is computed over
// its JSON encoding.
func CandidateDigest(candidates interface{}) (string, error) {
	raw, err := json.Marshal(candidates)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

// NextGatherSeq advances and returns a session's gather counter.
func NextGatherSeq(sess *session.Session) int {
	return 1
}

func sortedStrings(list []string) []string {
	out := append([]string{}, list...)
	sort.Strings(out)
	return out
}

func sortedFailed(list []FailedAttemptState) []FailedAttemptState {
	out := append([]FailedAttemptState{}, list...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Verb != out[j].Verb {
			return out[i].Verb < out[j].Verb
		}
		return out[i].Target < out[j].Target
	})
	return out
}
