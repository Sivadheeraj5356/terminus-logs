package journalspan

import (
	"encoding/json"
	"os"
)

type Report struct {
	Runs []ReportRow `json:"runs"`
}

func WriteReport(path string, runs []ReportRow) error {
	payload, err := json.MarshalIndent(Report{Runs: runs}, "", "  ")
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	return os.WriteFile(path, payload, 0o644)
}
