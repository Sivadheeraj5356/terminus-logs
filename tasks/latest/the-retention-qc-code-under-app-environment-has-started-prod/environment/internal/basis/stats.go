package basis

import (
	"sort"

	"ra.local/field/internal/domain"
)

func Median(values []float64) float64 {
	copyOf := append([]float64(nil), values...)
	sort.Float64s(copyOf)
	middle := len(copyOf) / 2
	if len(copyOf)%2 == 1 {
		return copyOf[middle]
	}
	return (copyOf[middle-1] + copyOf[middle]) / 2
}

func Fit(rows []domain.Observation, runs []string) domain.Model {
	byPeptide := make(map[string][]float64)
	for _, row := range rows {
		byPeptide[row.Peptide] = append(byPeptide[row.Peptide], row.Coordinate)
	}
	peptides := make([]string, 0, len(byPeptide))
	for peptide := range byPeptide {
		peptides = append(peptides, peptide)
	}
	sort.Strings(peptides)
	centers := make([]domain.Center, 0, len(peptides))
	for _, peptide := range peptides {
		values := byPeptide[peptide]
		centers = append(centers, domain.Center{
			Peptide: peptide, Value: Median(values), Support: len(values),
		})
	}
	return domain.Model{TrainingRuns: append([]string(nil), runs...), Centers: centers}
}
