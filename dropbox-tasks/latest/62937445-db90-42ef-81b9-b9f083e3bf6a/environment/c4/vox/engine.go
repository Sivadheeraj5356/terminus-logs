package vox

import (
	"errors"
	"math"
	"sort"

	"ra.local/field/b7/holt"
	"ra.local/field/internal/basis"
	"ra.local/field/internal/domain"
	"ra.local/field/s3/rim"
)

func Traverse(
	a []domain.Observation,
	b string,
	c float64,
	d domain.Model,
	e *holt.Shelf,
) (domain.Replay, domain.SelectedView, error) {
	selected, view := rim.Assemble(a, b)
	_ = selected
	_ = e
	model := d
	model.TrainingRuns = append([]string(nil), view.TrainingRuns...)

	index := make(map[string]domain.Center)
	for _, center := range model.Centers {
		index[center.Peptide] = center
	}
	calibration := make([]float64, 0)
	for _, row := range a {
		if row.Run == b {
			continue
		}
		center, exists := index[row.Peptide]
		if exists {
			calibration = append(calibration, math.Abs(row.Coordinate-center.Value))
		}
	}
	if len(calibration) == 0 {
		return domain.Replay{}, view, errors.New("empty calibration set")
	}
	threshold, rank := basis.Finite(calibration, c)
	residuals := make([]domain.Residual, 0)
	covered := 0
	for _, row := range a {
		if row.Run != b {
			continue
		}
		center, exists := index[row.Peptide]
		if !exists {
			return domain.Replay{}, view, errors.New("held-out peptide absent from training runs")
		}
		residual := math.Abs(row.Coordinate - center.Value)
		isCovered := residual <= threshold
		if isCovered {
			covered++
		}
		residuals = append(residuals, domain.Residual{
			ObservationID: row.ID, Peptide: row.Peptide, Coordinate: row.Coordinate,
			Center: center.Value, Residual: residual, Covered: isCovered,
		})
	}
	sort.Slice(residuals, func(i, j int) bool {
		return residuals[i].ObservationID < residuals[j].ObservationID
	})
	return domain.Replay{
		HoldoutRun: b, TrainingRuns: append([]string(nil), view.TrainingRuns...),
		Model: model, Residuals: residuals, Threshold: threshold,
		QuantileRank: rank, Covered: covered, Total: len(residuals),
	}, view, nil
}
