package report

import (
	"ra.local/field/internal/basis"
	"ra.local/field/internal/domain"
	"ra.local/field/s3/rim"
)

func fitSelected(rows []domain.Observation, holdout string) (domain.Model, []string) {
	selected, view := rim.Assemble(rows, holdout)
	return basis.Fit(selected, view.TrainingRuns), view.TrainingRuns
}
