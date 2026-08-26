// Package hintassemble implements stage two of the hint pipeline: reading a
// session's staged candidates.json, re-verifying its attestation digests
// against current state, and filtering staged candidates into live hints.
package hintassemble

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"time"

	"labyrinthoracle/internal/attest"
	"labyrinthoracle/internal/chronicle"
	"labyrinthoracle/internal/filters"
	"labyrinthoracle/internal/probe"
	"labyrinthoracle/internal/session"
)

// Hint is one live, filtered next-action suggestion.
type Hint struct {
	Kind   string `json:"kind"`
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

// Result is the response of assembling hints from a staged snapshot.
type Result struct {
	Hints       []Hint `json:"hints"`
	Refused     bool   `json:"refused,omitempty"`
	Reason      string `json:"reason,omitempty"`
	RouteDigest string `json:"route_digest,omitempty"`
}

func kindRank(kind string) int {
	switch kind {
	case "move":
		return 0
	case "action":
		return 1
	case "take":
		return 2
	default:
		return 99
	}
}

func toSessionState(view session.Snapshot) attest.SessionState {
	failed := make([]attest.FailedAttemptState, 0, len(view.Failed))
	for _, f := range view.Failed {
		failed = append(failed, attest.FailedAttemptState{Verb: f.Verb, Target: f.Target})
	}
	return attest.SessionState{
		WorldID:   view.WorldID,
		Room:      view.Room,
		Inventory: view.Inventory,
		Consumed:  view.Consumed,
		Failed:    failed,
	}
}

// Assemble reads sess's staged candidates.json, re-verifies its
// attestation digests against the session's current state, resolves the
// chronicle's forbidden rules, and filters the staged candidates into live
// hints.
func Assemble(sess *session.Session) (*Result, error) {
	view := sess.View()

	raw, err := os.ReadFile(probe.ScratchPath(view.ID))
	if err != nil {
		return &Result{Hints: []Hint{}, Refused: true, Reason: "missing-snapshot"}, nil
	}
	var snap probe.Snapshot
	if err := json.Unmarshal(raw, &snap); err != nil {
		return &Result{Hints: []Hint{}, Refused: true, Reason: "corrupt-snapshot"}, nil
	}

	recomputedCandDigest, err := attest.CandidateDigest(snap.Candidates)
	if err != nil {
		return nil, err
	}
	if recomputedCandDigest != snap.CandidateDigest {
		return &Result{Hints: []Hint{}, Refused: true, Reason: "candidate-digest-mismatch"}, nil
	}

	currentStateDigest, err := attest.SessionStateDigest(toSessionState(view))
	if err != nil {
		return nil, err
	}
	if currentStateDigest != snap.SessionStateSHA256 {
		return &Result{Hints: []Hint{}, Refused: true, Reason: "stale-session-state"}, nil
	}

	chroniclePath := chronicle.Resolve(view.WorldID)
	currentChronicleDigest, err := attest.ChronicleDigest(chroniclePath)
	if err != nil {
		return nil, err
	}
	if currentChronicleDigest != snap.ChronicleSHA256 {
		return &Result{Hints: []Hint{}, Refused: true, Reason: "chronicle-digest-mismatch"}, nil
	}

	hints := []Hint{}
	for _, c := range snap.Candidates {
		if !filters.InventoryOK(c.RequiredItems, view.Inventory) {
			continue
		}
		if c.Kind == "take" {
			if !filters.NotIn(c.Target, view.Inventory) {
				continue
			}
		} else {
			if !filters.NotIn(c.Target, view.Consumed) {
				continue
			}
		}
		hints = append(hints, Hint{Kind: c.Kind, Verb: c.Verb, Target: c.Target})
	}

	sort.SliceStable(hints, func(i, j int) bool {
		if kindRank(hints[i].Kind) != kindRank(hints[j].Kind) {
			return kindRank(hints[i].Kind) < kindRank(hints[j].Kind)
		}
		if hints[i].Verb != hints[j].Verb {
			return hints[i].Verb < hints[j].Verb
		}
		return hints[i].Target < hints[j].Target
	})

	if err := writeAssembleAck(view.ID, snap.GatherSeq); err != nil {
		return nil, err
	}
	return &Result{Hints: hints}, nil
}

func writeAssembleAck(sessionID string, gatherSeq int) error {
	ack := map[string]interface{}{
		"session_id":   sessionID,
		"gather_seq":   gatherSeq,
		"assembled_at": time.Now().UTC().Format(time.RFC3339),
	}
	raw, err := json.Marshal(ack)
	if err != nil {
		return err
	}
	dir := filepath.Dir(probe.AssembleAckPath(sessionID))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(probe.AssembleAckPath(sessionID), raw, 0o644)
}
