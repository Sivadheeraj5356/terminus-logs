// Package spread measures how far a family's mapped values sit from the
// observed accuracy on a rung, in equal-mass bins.
package spread

import (
	"sort"

	"plangen/internal/frac"
	"plangen/internal/model"
	"plangen/tabulate"
)

// Cuts returns the m-1 equal-mass edge values for a family, taken from the rows
// it is handed.
func Cuts(bk tabulate.Book, pick int, rows []model.Row, unit, m int) []int {
	vals := make([]int, 0, len(rows))
	for _, r := range rows {
		vals = append(vals, bk.Eval(pick, r.Raw, r.Lane))
	}
	sort.Ints(vals)
	n := len(vals)
	edges := make([]int, 0, m-1)
	for j := 1; j < m; j++ {
		idx := j * n / m
		if idx >= n {
			idx = n - 1
		}
		if idx < 0 {
			idx = 0
		}
		edges = append(edges, vals[idx])
	}
	return edges
}

func binOf(c int, cuts []int) int {
	return sort.SearchInts(cuts, c+1)
}

// Tally returns the integer gap between a family's mapped values and the
// observed accuracy over a rung, summed across equal-mass bins.
func Tally(bk tabulate.Book, pick int, rows []model.Row, cuts []int, unit int) int {
	m := len(cuts) + 1
	local := Cuts(bk, pick, rows, unit, m)
	nb := make([]int, m)
	hb := make([]int, m)
	sc := make([]int, m)
	for _, r := range rows {
		c := bk.Eval(pick, r.Raw, r.Lane)
		b := binOf(c, local)
		nb[b]++
		hb[b] += r.Hit
		sc[b] += c
	}
	total := 0
	for b := 0; b < m; b++ {
		if nb[b] == 0 {
			continue
		}
		seen := frac.RoundDiv(unit*hb[b], nb[b])
		held := frac.RoundDiv(sc[b], nb[b])
		total += nb[b] * frac.Abs(seen-held)
	}
	return total
}
