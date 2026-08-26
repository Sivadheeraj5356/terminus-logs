package main

// FlatConfig is an alternate flat config layout.
type FlatConfig struct {
	PeriodID       string `json:"period_id"`
	StartInclusive string `json:"start_inclusive"`
	EndExclusive   string `json:"end_exclusive"`
	Currency       string `json:"currency"`
}
