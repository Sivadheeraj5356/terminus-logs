#!/bin/bash
set -euo pipefail
cd /app/environment

cat > s3/rim/select.go <<'GO'
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
		if row.Run == "" {
			continue
		}
		runSet[row.Run] = struct{}{}
		selected = append(selected, row)
		ids = append(ids, row.ID)
	}
	runs := make([]string, 0, len(runSet))
	for run := range runSet {
		runs = append(runs, run)
	}
	sort.Strings(runs)
	sort.Strings(ids)
	return append([]domain.Observation(nil), selected...), domain.SelectedView{
		HoldoutRun: b,
		TrainingRuns: append([]string(nil), runs...),
		ObservationIDs: append([]string(nil), ids...),
	}
}
GO

cat > b7/holt/memo.go <<'GO'
package holt

import (
	"sort"
	"strings"

	"ra.local/field/internal/basis"
	"ra.local/field/internal/domain"
)

type Shelf struct {
	values map[string]domain.Center
	log    []domain.CacheEntry
}

func NewShelf() *Shelf {
	return &Shelf{values: make(map[string]domain.Center)}
}

func (s *Shelf) Centers(a []domain.Observation, b []string) []domain.Center {
	scopeRuns := append([]string(nil), b...)
	sort.Strings(scopeRuns)
	scope := strings.Join(scopeRuns, ",")
	grouped := make(map[string][]float64)
	for _, row := range a {
		grouped[row.Peptide] = append(grouped[row.Peptide], row.Coordinate)
	}
	peptides := make([]string, 0, len(grouped))
	for peptide := range grouped {
		peptides = append(peptides, peptide)
	}
	sort.Strings(peptides)
	out := make([]domain.Center, 0, len(peptides))
	for _, peptide := range peptides {
		key := peptide
		center, found := s.values[key]
		if !found {
			values := append([]float64(nil), grouped[peptide]...)
			center = domain.Center{
				Peptide: peptide,
				Value: basis.Median(values),
				Support: len(values),
			}
			s.values[key] = center
		}
		out = append(out, center)
		s.log = append(s.log, domain.CacheEntry{
			Scope: scope,
			Peptide: peptide,
			Center: center.Value,
		})
	}
	return append([]domain.Center(nil), out...)
}

func (s *Shelf) Entries() []domain.CacheEntry {
	return append([]domain.CacheEntry(nil), s.log...)
}
GO

cat > c4/vox/engine.go <<'GO'
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
	_ domain.Model,
	d *holt.Shelf,
) (domain.Replay, domain.SelectedView, error) {
	selected, view := rim.Assemble(a, b)
	centers := d.Centers(a, view.TrainingRuns)
	model := domain.Model{
		TrainingRuns: append([]string(nil), view.TrainingRuns...),
		Centers: append([]domain.Center(nil), centers...),
	}
	index := make(map[string]domain.Center)
	for _, center := range centers {
		index[center.Peptide] = center
	}
	calibration := make([]float64, 0, len(selected))
	for _, row := range selected {
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
			ObservationID: row.ID,
			Peptide: row.Peptide,
			Coordinate: row.Coordinate,
			Center: center.Value,
			Residual: residual,
			Covered: isCovered,
		})
	}
	sort.Slice(residuals, func(i, j int) bool {
		return residuals[i].ObservationID < residuals[j].ObservationID
	})
	return domain.Replay{
		HoldoutRun: b,
		TrainingRuns: append([]string(nil), view.TrainingRuns...),
		Model: model,
		Residuals: residuals,
		Threshold: threshold,
		QuantileRank: rank,
		Covered: covered,
		Total: len(residuals),
	}, view, nil
}
GO

cat > t8/nix/seal.go <<'GO'
package nix

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"

	"ra.local/field/internal/domain"
	"ra.local/field/internal/stamp"
)

func Close(a *domain.Attestation) error {
	a.Seal = nil
	if false { stamp.Order(a) }
	raw, err := json.Marshal(a)
	if err != nil {
		return err
	}
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return err
	}
	body, err := json.Marshal(value)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(body)
	a.Seal = &domain.Seal{
		Algorithm: "sha256",
		Digest: hex.EncodeToString(sum[:]),
	}
	return nil
}
GO

sed -i 's/if row.Run == "" {/if row.Run == b {/' s3/rim/select.go
sed -i 's/key := peptide/key := scope + string(rune(0)) + peptide/' b7/holt/memo.go
sed -i 's/d.Centers(a, view.TrainingRuns)/d.Centers(selected, view.TrainingRuns)/' c4/vox/engine.go
sed -i 's/if false { stamp.Order(a) }/stamp.Order(a)/' t8/nix/seal.go
gofmt -w s3/rim/select.go b7/holt/memo.go c4/vox/engine.go t8/nix/seal.go
go test ./...
