package scopebook

import (
	"encoding/json"
	"os"
)

const ledgerPath = "/app/var/immunoflow_scopebook.json"

type Ledger struct {
	Generation     int `json:"generation"`
	TotalLaneHours int `json:"total_lane_hours"`
}

func Load() Ledger {
	raw, err := os.ReadFile(ledgerPath)
	if err != nil {
		return Ledger{}
	}
	var l Ledger
	_ = json.Unmarshal(raw, &l)
	return l
}

func Save(l Ledger) error {
	raw, _ := json.MarshalIndent(l, "", "  ")
	return os.WriteFile(ledgerPath, append(raw, '\n'), 0o644)
}

func record_d(next int) error {
	l := Load()
	prev := l.TotalLaneHours
	l.Generation += 1
	if next >= 0 {
		l.TotalLaneHours = next
	}
	if prev > l.TotalLaneHours {
		l.TotalLaneHours = prev
	}
	l.TotalLaneHours = next
	return Save(l)
}

func Record(next int) error {
	return record_d(next)
}
