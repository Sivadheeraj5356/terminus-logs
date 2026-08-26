// Package probe implements stage one of the hint pipeline: gathering raw,
// unfiltered candidates for a session's current room and writing them to a
// hint snapshot on disk for the assemble lane to later verify and filter.
package probe

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"labyrinthoracle/internal/attest"
	"labyrinthoracle/internal/session"
	"labyrinthoracle/internal/worldmap"
)

// Candidate is one raw, unfiltered hint possibility gathered from the
// current room's exits, actions, or items, before any inventory, consumed,
// or forbidden-rule filtering is applied.
type Candidate struct {
	Kind          string   `json:"kind"`
	Verb          string   `json:"verb"`
	Target        string   `json:"target"`
	RequiredItems []string `json:"required_items"`
	OrderSeq      int      `json:"order_seq"`
}

// Snapshot is the staged candidates.json contract documented in
// /app/docs/snapshot-attestation.md.
type Snapshot struct {
	SessionID          string      `json:"session_id"`
	Room               string      `json:"room"`
	WorldID            string      `json:"world_id"`
	GatherSeq          int         `json:"gather_seq"`
	ChronicleSHA256    string      `json:"chronicle_sha256"`
	SessionStateSHA256 string      `json:"session_state_sha256"`
	CandidateDigest    string      `json:"candidate_digest"`
	Candidates         []Candidate `json:"candidates"`
}

// ScratchRoot is where per-session hint snapshots are written.
const ScratchRoot = "/app/hint-scratch"

// ScratchPath returns the candidates.json path for a session.
func ScratchPath(sessionID string) string {
	return filepath.Join(ScratchRoot, sessionID, "candidates.json")
}

// AssembleAckPath returns the assemble_ack.json path for a session.
func AssembleAckPath(sessionID string) string {
	return filepath.Join(ScratchRoot, sessionID, "assemble_ack.json")
}

// AbortPath returns the abort.json path for a session.
func AbortPath(sessionID string) string {
	return filepath.Join(ScratchRoot, sessionID, "abort.json")
}

// RouteSealPath returns the route-seal.json path for a session.
func RouteSealPath(sessionID string) string {
	return filepath.Join(ScratchRoot, sessionID, "route-seal.json")
}

// Gather walks the current room's exits, actions, and items into raw
// candidates, ordered ascending by each source's ID within its category
// (exits, then actions, then items).
func Gather(room string, world *worldmap.World) []Candidate {
	var out []Candidate
	seq := 1
	out, seq = appendMoveCandidates(out, seq, world.ExitsInRoomAscending(room))
	out, seq = appendActionCandidates(out, seq, world.ActionsInRoomAscending(room))
	out, seq = appendTakeCandidates(out, seq, world.ItemsInRoomAscending(room))
	return out
}

func appendMoveCandidates(out []Candidate, seq int, exits []worldmap.Exit) ([]Candidate, int) {
	for _, e := range exits {
		out = append(out, Candidate{
			Kind:          "move",
			Verb:          e.Verb,
			Target:        e.To,
			RequiredItems: copyStrings(e.RequiredItems),
			OrderSeq:      seq,
		})
		seq++
	}
	return out, seq
}

func appendActionCandidates(out []Candidate, seq int, actions []worldmap.Action) ([]Candidate, int) {
	for _, a := range actions {
		out = append(out, Candidate{
			Kind:          "action",
			Verb:          a.Verb,
			Target:        a.Target,
			RequiredItems: copyStrings(a.RequiredItems),
			OrderSeq:      seq,
		})
		seq++
	}
	return out, seq
}

func appendTakeCandidates(out []Candidate, seq int, items []worldmap.Item) ([]Candidate, int) {
	for _, it := range items {
		out = append(out, Candidate{
			Kind:          "take",
			Verb:          "take",
			Target:        it.ID,
			RequiredItems: []string{},
			OrderSeq:      seq,
		})
		seq++
	}
	return out, seq
}

func copyStrings(in []string) []string {
	if len(in) == 0 {
		return []string{}
	}
	out := make([]string, len(in))
	copy(out, in)
	return out
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

// WriteSnapshot gathers raw candidates for sess's current room, computes
// its attestation digests, and writes the hint snapshot to disk.
func WriteSnapshot(sess *session.Session, world *worldmap.World, chroniclePath string) (*Snapshot, error) {
	view := sess.View()
	candidates := Gather(view.Room, world)

	chronicleDigest, err := attest.ChronicleDigest(chroniclePath)
	if err != nil {
		return nil, fmt.Errorf("probe: chronicle digest: %w", err)
	}
	stateDigest, err := attest.SessionStateDigest(toSessionState(view))
	if err != nil {
		return nil, fmt.Errorf("probe: session state digest: %w", err)
	}
	candDigest, err := attest.CandidateDigest(candidates)
	if err != nil {
		return nil, fmt.Errorf("probe: candidate digest: %w", err)
	}

	snap := &Snapshot{
		SessionID:          view.ID,
		Room:               view.Room,
		WorldID:            view.WorldID,
		GatherSeq:          attest.NextGatherSeq(sess),
		ChronicleSHA256:    chronicleDigest,
		SessionStateSHA256: stateDigest,
		CandidateDigest:    candDigest,
		Candidates:         candidates,
	}

	dir := filepath.Dir(ScratchPath(view.ID))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, fmt.Errorf("probe: mkdir scratch dir: %w", err)
	}
	raw, err := json.Marshal(snap)
	if err != nil {
		return nil, fmt.Errorf("probe: marshal snapshot: %w", err)
	}
	if err := os.WriteFile(ScratchPath(view.ID), raw, 0o644); err != nil {
		return nil, fmt.Errorf("probe: write snapshot: %w", err)
	}
	return snap, nil
}
