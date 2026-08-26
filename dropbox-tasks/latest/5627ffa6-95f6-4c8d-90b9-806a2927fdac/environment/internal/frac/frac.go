// Package frac provides exact integer helpers so every stage agrees on one
// arithmetic without any floating point.
package frac

// RoundDiv returns round-half-up of num/den for den > 0. It is defined as
// floor((2*num + den) / (2*den)) using integer division, which rounds .5 up.
func RoundDiv(num, den int) int {
	if den <= 0 {
		return 0
	}
	return (2*num + den) / (2 * den)
}

// Less reports whether a/da < b/db for positive denominators, using
// cross-multiplication so no rounding is involved.
func Less(a, da, b, db int) bool {
	return a*db < b*da
}

// Abs returns the absolute value of x.
func Abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
