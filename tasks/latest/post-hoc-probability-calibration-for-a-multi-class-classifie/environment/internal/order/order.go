// Package order provides deterministic ordering helpers so results never depend
// on map iteration or unstable sorts.
package order

import "sort"

// SortedInts returns a new ascending copy of the input.
func SortedInts(xs []int) []int {
	out := make([]int, len(xs))
	copy(out, xs)
	sort.Ints(out)
	return out
}

// UniqueAscending returns the sorted distinct values of the input.
func UniqueAscending(xs []int) []int {
	s := SortedInts(xs)
	out := s[:0]
	for i, v := range s {
		if i == 0 || v != s[i-1] {
			out = append(out, v)
		}
	}
	return out
}
