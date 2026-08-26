package main

// nearestRank returns the nearest-rank percentile value.
// rank = ceil(q * n), 1-indexed into the sorted slice.
// Agents must implement this function. See /docs/statistics-spec.md.
func nearestRank(sorted []float64, q float64) float64 {
	return 0
}

// popStdDev computes population standard deviation.
// Agents must implement this function. See /docs/statistics-spec.md.
func popStdDev(values []float64) float64 {
	return 0
}

// sortedCopy returns a sorted copy of the input slice.
// Agents must implement this function.
func sortedCopy(values []float64) []float64 {
	return nil
}
