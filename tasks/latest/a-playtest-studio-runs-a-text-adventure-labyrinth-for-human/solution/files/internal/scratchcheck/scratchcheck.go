// Package scratchcheck verifies staged hint-scratch artifacts for the check CLI.
package scratchcheck

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"labyrinthoracle/internal/attest"
	"labyrinthoracle/internal/probe"
)

type hintLine struct {
	Kind   string `json:"kind"`
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

type assembleAck struct {
	SessionID   string     `json:"session_id"`
	GatherSeq   int        `json:"gather_seq"`
	Hints       []hintLine `json:"hints"`
	RouteDigest string     `json:"route_digest"`
}

type routeSeal struct {
	SessionID       string `json:"session_id"`
	GatherSeq       int    `json:"gather_seq"`
	HintCount       int    `json:"hint_count"`
	CandidateDigest string `json:"candidate_digest"`
	RouteDigest     string `json:"route_digest"`
}

type abortTicket struct {
	SessionID   string `json:"session_id"`
	GatherSeq   int    `json:"gather_seq"`
	Reason      string `json:"reason"`
	AbortDigest string `json:"abort_digest"`
}

func routeDigestHex(hints []hintLine) string {
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

// CheckDigest recomputes candidate_digest from candidates.json in dir.
func CheckDigest(dir string) error {
	raw, err := os.ReadFile(filepath.Join(dir, "candidates.json"))
	if err != nil {
		return err
	}
	var snap probe.Snapshot
	if err := json.Unmarshal(raw, &snap); err != nil {
		return err
	}
	got, err := attest.CandidateDigest(snap.Candidates)
	if err != nil {
		return err
	}
	if got != snap.CandidateDigest {
		return fmt.Errorf("candidate digest mismatch")
	}
	return nil
}

// CheckRoute verifies assemble_ack and route-seal route digests.
func CheckRoute(dir string) error {
	ackRaw, err := os.ReadFile(filepath.Join(dir, "assemble_ack.json"))
	if err != nil {
		return err
	}
	var ack assembleAck
	if err := json.Unmarshal(ackRaw, &ack); err != nil {
		return err
	}
	sealRaw, err := os.ReadFile(filepath.Join(dir, "route-seal.json"))
	if err != nil {
		return err
	}
	var seal routeSeal
	if err := json.Unmarshal(sealRaw, &seal); err != nil {
		return err
	}
	expected := routeDigestHex(ack.Hints)
	if expected != ack.RouteDigest {
		return fmt.Errorf("assemble_ack route_digest mismatch")
	}
	if expected != seal.RouteDigest {
		return fmt.Errorf("route-seal route_digest mismatch")
	}
	if ack.GatherSeq != seal.GatherSeq {
		return fmt.Errorf("gather_seq mismatch")
	}
	if seal.HintCount != len(ack.Hints) {
		return fmt.Errorf("hint_count mismatch")
	}
	return nil
}

// CheckAbort verifies abort.json when present.
func CheckAbort(dir string) error {
	path := filepath.Join(dir, "abort.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	var ticket abortTicket
	if err := json.Unmarshal(raw, &ticket); err != nil {
		return err
	}
	expected := abortDigestHex(ticket.SessionID, ticket.GatherSeq, ticket.Reason)
	if expected != ticket.AbortDigest {
		return fmt.Errorf("abort_digest mismatch")
	}
	return nil
}
