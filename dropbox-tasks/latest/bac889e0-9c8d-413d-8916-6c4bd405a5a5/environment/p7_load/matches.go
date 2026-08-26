package p7_load

import (
	"encoding/json"
	"os"

	"balance_lab/p9_types"
)

func ReadMatches(path string) ([]p9_types.MatchRow, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rows []p9_types.MatchRow
	if err := json.Unmarshal(raw, &rows); err != nil {
		return nil, err
	}
	return rows, nil
}
