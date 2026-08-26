package bundlewalk
// Bundlewalk reads CT log rows and certificate metadata into merkle snapshot rows.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"github.com/privco/ctpki/internal/pkitypes"
	"github.com/privco/ctpki/internal/serialdup"
)

func Run(bundleRoot, snapshotPath string) error {
	metaPath := filepath.Join(bundleRoot, "bundle_meta.json")
	metaBytes, err := os.ReadFile(metaPath)
	if err != nil {
		return err
	}
	var meta struct {
		BundleID string `json:"bundle_id"`
	}
	if err := json.Unmarshal(metaBytes, &meta); err != nil {
		return err
	}
	issuance, err := serialdup.LoadIssuance(filepath.Join(bundleRoot, "issuance.json"))
	if err != nil {
		return err
	}
	bySerial := map[string][]serialdup.IssuanceRow{}
	for _, row := range issuance {
		bySerial[row.Serial] = append(bySerial[row.Serial], row)
	}
	for serial := range bySerial {
		sort.Slice(bySerial[serial], func(i, j int) bool {
			return bySerial[serial][i].IssuedAt > bySerial[serial][j].IssuedAt
		})
	}
	seen := map[string]int{}

	entriesPath := filepath.Join(bundleRoot, "ct_logs", "b161aa7f_entries.jsonl")
	entriesBytes, err := os.ReadFile(entriesPath)
	if err != nil {
		return err
	}
	var rows []pkitypes.MerkleRow
	for _, line := range splitLines(string(entriesBytes)) {
		if line == "" {
			continue
		}
		var e pkitypes.CTEntry
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			return err
		}
		filename := e.Serial + ".json"
		options := bySerial[e.Serial]
		if len(options) == 1 {
			filename = options[0].Filename
		} else if len(options) > 0 {
			idx := seen[e.Serial]
			filename = options[idx].Filename
			seen[e.Serial] = idx + 1
		}
		rows = append(rows, pkitypes.MerkleRow{
			Serial:    e.Serial,
			Filename:  filename,
			LeafIndex: e.LeafIndex,
			LeafHash:  e.LeafHash,
		})
	}
	snap := pkitypes.MerkleSnapshot{BundleID: meta.BundleID, Rows: rows}
	out, err := json.MarshalIndent(snap, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(snapshotPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(snapshotPath, append(out, '\n'), 0o644)
}

func ReadSnapshot(snapshotPath string) (pkitypes.MerkleSnapshot, error) {
	b, err := os.ReadFile(snapshotPath)
	if err != nil {
		return pkitypes.MerkleSnapshot{}, err
	}
	var snap pkitypes.MerkleSnapshot
	return snap, json.Unmarshal(b, &snap)
}

func splitLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}
