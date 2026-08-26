package validate

import (
	"encoding/csv"
	"encoding/json"
	"os"
	"strings"
)

func ValidateShape(dailyPath, weeklyPath, escrowPath string) error {
	daily, err := os.ReadFile(dailyPath)
	if err != nil {
		return err
	}
	weekly, err := os.ReadFile(weeklyPath)
	if err != nil {
		return err
	}
	escrow, err := os.ReadFile(escrowPath)
	if err != nil {
		return err
	}
	dr := csv.NewReader(strings.NewReader(string(daily)))
	dHeader, err := dr.Read()
	if err != nil || len(dHeader) < 8 {
		return os.ErrInvalid
	}
	wr := csv.NewReader(strings.NewReader(string(weekly)))
	wHeader, err := wr.Read()
	if err != nil || len(wHeader) < 7 {
		return os.ErrInvalid
	}
	for _, line := range strings.Split(strings.TrimSpace(string(escrow)), "\n") {
		if line == "" {
			continue
		}
		var obj map[string]any
		if json.Unmarshal([]byte(line), &obj) != nil {
			return os.ErrInvalid
		}
	}
	return nil
}
