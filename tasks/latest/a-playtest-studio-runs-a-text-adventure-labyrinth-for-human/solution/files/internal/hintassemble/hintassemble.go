// Package hintassemble implements stage two of the hint pipeline: reading a
// session's staged candidates.json, re-verifying its attestation digests
// against current state, and filtering staged candidates into live hints.
package hintassemble

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"labyrinthoracle/internal/attest"
	"labyrinthoracle/internal/chronicle"
	"labyrinthoracle/internal/filters"
	"labyrinthoracle/internal/probe"
	"labyrinthoracle/internal/rules"
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

// RouteDigestHex hashes hints in returned order as kind:verb:target lines.
func RouteDigestHex(hints []Hint) string {
	lines := make([]string, 0, len(hints))
	for _, h := range hints {
		lines = append(lines, h.Kind+":"+h.Verb+":"+h.Target)
	}
	body := strings.Join(lines, "\n")
	sum := sha256.Sum256([]byte(body))
	return hex.EncodeToString(sum[:])
}

func abortDigestHex(sessionID string, gatherSeq int, reason string) string {
	body := fmt.Sprintf("%s:%d:%s", sessionID, gatherSeq, reason)
	sum := sha256.Sum256([]byte(body))
	return hex.EncodeToString(sum[:])
}

func writeAbort(sessionID string, gatherSeq int, reason string) error {
	payload := map[string]interface{}{
		"session_id":   sessionID,
		"gather_seq":   gatherSeq,
		"reason":       reason,
		"abort_digest": abortDigestHex(sessionID, gatherSeq, reason),
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	dir := filepath.Dir(probe.AbortPath(sessionID))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	_ = os.Remove(probe.AssembleAckPath(sessionID))
	_ = os.Remove(probe.RouteSealPath(sessionID))
	return os.WriteFile(probe.AbortPath(sessionID), raw, 0o644)
}

func clearAbort(sessionID string) {
	_ = os.Remove(probe.AbortPath(sessionID))
}

func refuse(sessionID string, gatherSeq int, reason string) (*Result, error) {
	if err := writeAbort(sessionID, gatherSeq, reason); err != nil {
		return nil, err
	}
	return &Result{Hints: []Hint{}, Refused: true, Reason: reason}, nil
}

// Assemble reads sess's staged candidates.json, re-verifies its
// attestation digests against the session's current state, resolves the
// chronicle's forbidden rules, and filters the staged candidates into live
// hints.
func Assemble(sess *session.Session) (*Result, error) {
	view := sess.View()

	raw, err := os.ReadFile(probe.ScratchPath(view.ID))
	if err != nil {
		return refuse(view.ID, 0, "missing-snapshot")
	}
	var snap probe.Snapshot
	if err := json.Unmarshal(raw, &snap); err != nil {
		return refuse(view.ID, 0, "corrupt-snapshot")
	}

	recomputedCandDigest, err := attest.CandidateDigest(snap.Candidates)
	if err != nil {
		return nil, err
	}
	if recomputedCandDigest != snap.CandidateDigest {
		return refuse(view.ID, snap.GatherSeq, "candidate-digest-mismatch")
	}

	currentStateDigest, err := attest.SessionStateDigest(toSessionState(view))
	if err != nil {
		return nil, err
	}
	if currentStateDigest != snap.SessionStateSHA256 {
		return refuse(view.ID, snap.GatherSeq, "stale-session-state")
	}

	chroniclePath := chronicle.Resolve(view.WorldID)
	currentChronicleDigest, err := attest.ChronicleDigest(chroniclePath)
	if err != nil {
		return nil, err
	}
	if currentChronicleDigest != snap.ChronicleSHA256 {
		return refuse(view.ID, snap.GatherSeq, "chronicle-digest-mismatch")
	}

	chronicleText, err := os.ReadFile(chroniclePath)
	if err != nil {
		return nil, err
	}
	forbidden := rules.Load(string(chronicleText))

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
		if rules.ForbiddenIn(forbidden, view.Room, c.Verb, c.Target) {
			continue
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

	routeDigest := RouteDigestHex(hints)
	clearAbort(view.ID)
	if err := writeAssembleArtifacts(view.ID, snap.GatherSeq, snap.CandidateDigest, hints, routeDigest); err != nil {
		return nil, err
	}
	return &Result{Hints: hints, RouteDigest: routeDigest}, nil
}

func writeAssembleArtifacts(sessionID string, gatherSeq int, candidateDigest string, hints []Hint, routeDigest string) error {
	dir := filepath.Dir(probe.AssembleAckPath(sessionID))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	ack := map[string]interface{}{
		"session_id":   sessionID,
		"gather_seq":   gatherSeq,
		"assembled_at": time.Now().UTC().Format(time.RFC3339),
		"hints":        hints,
		"route_digest": routeDigest,
	}
	raw, err := json.Marshal(ack)
	if err != nil {
		return err
	}
	if err := os.WriteFile(probe.AssembleAckPath(sessionID), raw, 0o644); err != nil {
		return err
	}
	seal := map[string]interface{}{
		"session_id":       sessionID,
		"gather_seq":       gatherSeq,
		"hint_count":       len(hints),
		"candidate_digest": candidateDigest,
		"route_digest":     routeDigest,
	}
	sealRaw, err := json.Marshal(seal)
	if err != nil {
		return err
	}
	return os.WriteFile(probe.RouteSealPath(sessionID), sealRaw, 0o644)
}
