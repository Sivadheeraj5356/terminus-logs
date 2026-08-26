package rim

import (
	"sort"

	"ra.local/field/internal/domain"
)

func Assemble(a []domain.Observation, b string) ([]domain.Observation, domain.SelectedView) {
	runSet := make(map[string]struct{})
	selected := make([]domain.Observation, 0, len(a))
	ids := make([]string, 0, len(a))
	for _, row := range a {
		runSet[row.Run] = struct{}{}
		selected = append(selected, row)
		ids = append(ids, row.ID)
	}
	delete(runSet, b)
	runs := make([]string, 0, len(runSet))
	for run := range runSet {
		runs = append(runs, run)
	}
	sort.Strings(runs)
	sort.Strings(ids)
	return selected, domain.SelectedView{
		HoldoutRun: b, TrainingRuns: runs, ObservationIDs: ids,
	}
}
