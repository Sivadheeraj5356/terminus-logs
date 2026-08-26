package serialdup

import (
	"encoding/json"
	"os"
)

type IssuanceRow struct {
	Serial   string `json:"serial"`
	IssuedAt string `json:"issued_at"`
	Filename string `json:"filename"`
}

type issuanceRow = IssuanceRow

// KeepNewest returns true when candidate wins a serial collision.
// Baseline keeps the lexicographically smaller issued_at string.
func KeepNewest(candidate, incumbent issuanceRow) bool {
	return candidate.IssuedAt < incumbent.IssuedAt
}

func LoadIssuance(path string) ([]issuanceRow, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var f struct {
		Issuance []issuanceRow `json:"issuance"`
	}
	if err := json.Unmarshal(b, &f); err != nil {
		return nil, err
	}
	return f.Issuance, nil
}
