package export

import (
	"encoding/json"
	"os"
	"s9d/internal/session"
	"sort"
)

type Report struct {
	Rows []session.ReportRow `json:"rows"`
}

func WriteReport(path string, rows []session.ReportRow) error {
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].SeedID < rows[j].SeedID
	})
	doc := Report{Rows: rows}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}
