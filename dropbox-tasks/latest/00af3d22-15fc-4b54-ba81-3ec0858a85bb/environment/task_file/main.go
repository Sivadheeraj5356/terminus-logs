package main

import (
	"encoding/json"
	"os"
)

func main() {
	_ = os.MkdirAll("/app/output", 0755)
	report := map[string]any{
		"evaluated_at": 0,
		"decisions":    []any{},
		"summary": map[string]any{
			"allowed":       0,
			"denied":        0,
			"reason_counts": map[string]int{},
		},
	}
	data, _ := json.MarshalIndent(report, "", "  ")
	_ = os.WriteFile("/app/output/report.json", data, 0644)
}
