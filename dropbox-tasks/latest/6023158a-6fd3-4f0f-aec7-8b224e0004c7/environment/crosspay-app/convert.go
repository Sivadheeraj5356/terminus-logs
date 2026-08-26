package main

import "fmt"

// ConvertToBase converts an amount in micro-units of the `from` currency into
// micro-units of the reporting base currency, routing through the pivot currency
// (see docs/spec.md for the pivot, the leg order and the rounding). Returns an
// error when the currency is not in PivotRate.
//
// Stub: the real computation is supplied by the solution.
func ConvertToBase(amount int64, from string) (int64, error) {
	_, _ = amount, from
	return 0, fmt.Errorf("not_implemented")
}
