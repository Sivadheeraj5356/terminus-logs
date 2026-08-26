package audit

import (
	"errors"

	"ra.local/field/internal/domain"
)

func CheckRuns(runs []domain.RunRecord) error {
	seen := make(map[string]struct{})
	for _, record := range runs {
		if record.Run == "" || len(record.ObservationIDs) == 0 {
			return errors.New("incomplete run record")
		}
		if _, exists := seen[record.Run]; exists {
			return errors.New("duplicate run record")
		}
		seen[record.Run] = struct{}{}
	}
	return nil
}
