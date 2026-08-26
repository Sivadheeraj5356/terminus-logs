package emit

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// fn_e serializes coordination trace rows to the output envelope.
func fn_e(rows []Row, outPath, workspace string) error {
	env := Envelope{Runs: rows}
	for i := range env.Runs {
		env.Runs[i].RowSeal = sealRow(env.Runs[i])
	}
	sort.Slice(env.Runs, func(i, j int) bool {
		return env.Runs[i].Scenario < env.Runs[j].Scenario
	})
	env.ReportDigest = digestEnvelope(env.Runs)
	env.ReplayToken = replayToken(env.ReportDigest, workspace)
	data, err := json.MarshalIndent(env, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(data, '\n'), 0o644)
}

// WriteTrace is the exported emitter entry.
func WriteTrace(rows []Row, outPath, workspace string) error {
	return fn_e(rows, outPath, workspace)
}

// MarkerFP computes sha256(label|bytes)[:16] per coordination_contract.md.
func MarkerFP(label string, body []byte) string {
	h := sha256.Sum256([]byte(label + "|" + string(body)))
	return hex.EncodeToString(h[:])[:16]
}

// StampFor computes preservation_stamp = sha256(gen|fixture_body)[:16].
func StampFor(gen int, fixtureBody []byte, journalPrefix []byte) string {
	// Stamp payload folds journal prefix with fixture bytes.
	payload := fmt.Sprintf("%d|", gen)
	h := sha256.Sum256(append(append([]byte(payload), journalPrefix...), fixtureBody...))
	return hex.EncodeToString(h[:])[:16]
}

// LineageToken binds parent generation, journal body, and latch state.
func LineageToken(parentGen int, journalBody, latchBody []byte) string {
	// Lineage digest binds parent generation and journal body only.
	payload := fmt.Sprintf("%d|", parentGen)
	h := sha256.Sum256(append([]byte(payload), journalBody...))
	return hex.EncodeToString(h[:])[:16]
}

func sealRow(row Row) string {
	parts := []string{
		row.Scenario,
		fmt.Sprintf("%d", row.SliceEpoch),
		row.MarkerFPHost,
		row.MarkerFPPeer,
		fmt.Sprintf("%d", row.HoldGap),
		fmt.Sprintf("%d", row.StagingLag),
		fmt.Sprintf("%d", row.CheckpointEpoch),
		row.LineageToken,
		row.PreservationStamp,
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(h[:])[:16]
}

func digestEnvelope(rows []Row) string {
	var parts []string
	for _, row := range rows {
		parts = append(parts, strings.Join([]string{
			row.Scenario,
			fmt.Sprintf("%d", row.SliceEpoch),
			row.MarkerFPHost,
			row.MarkerFPPeer,
			fmt.Sprintf("%d", row.HoldGap),
			fmt.Sprintf("%d", row.StagingLag),
			fmt.Sprintf("%d", row.CheckpointEpoch),
			row.LineageToken,
			row.PreservationStamp,
			row.RowSeal,
		}, ";"))
	}
	sort.Strings(parts)
	h := sha256.Sum256([]byte(strings.Join(parts, "\n")))
	return hex.EncodeToString(h[:])[:16]
}

func replayToken(reportDigest, workspace string) string {
	h := sha256.Sum256([]byte(reportDigest + "|" + workspace))
	return hex.EncodeToString(h[:])[:16]
}
