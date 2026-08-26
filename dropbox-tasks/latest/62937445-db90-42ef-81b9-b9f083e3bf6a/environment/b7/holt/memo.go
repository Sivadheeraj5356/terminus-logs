package holt

import (
	"fmt"
	"sort"

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
			center = domain.Center{
				Peptide: peptide,
				Value:   basis.Median(grouped[peptide]),
				Support: len(grouped[peptide]),
			}
			s.values[key] = center
		}
		out = append(out, center)
		s.log = append(s.log, domain.CacheEntry{
			Scope: fmt.Sprint(b), Peptide: peptide, Center: center.Value,
		})
	}
	return out
}

func (s *Shelf) Entries() []domain.CacheEntry {
	return append([]domain.CacheEntry(nil), s.log...)
}
