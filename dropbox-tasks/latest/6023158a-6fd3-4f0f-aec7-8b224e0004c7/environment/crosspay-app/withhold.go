package main

import "fmt"

// RoundExact returns num/den as a single integer using exact integer math, with
// no floating point involved at any step. The rounding convention it must use
// is the one documented for the pivot conversion and the social-contribution
// base in docs/spec.md; every caller in this codebase that turns a fraction
// into a whole number of micro-units or minor units shares this one routine so
// the convention stays consistent everywhere it is applied.
//
// Stub: the real computation is supplied by the solution.
func RoundExact(num, den int64) int64 {
	_, _ = num, den
	return 0
}

// WithholdRegion returns the total marginal withholding in integer micro-units
// for the given gross under the named region's statutory schedule.
//
// Stub: the real computation is supplied by the solution.
func WithholdRegion(gross int64, region string) (int64, error) {
	_, _ = gross, region
	return 0, fmt.Errorf("not_implemented")
}
