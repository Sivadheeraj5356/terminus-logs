package main

// CountryAgg is one country's aggregated cost line for the report. Code is the
// ISO country code, Currency the country's own currency, Count the number of
// employees assigned there, LocalCost the summed employer cost in micro-units of
// the local currency, and BaseCost that total converted to the reporting base
// currency.
type CountryAgg struct {
	Code      string
	Currency  string
	Count     int
	LocalCost int64
	BaseCost  int64
}

// RankCountries returns the rows ordered for the report: by BaseCost descending,
// then by Count descending, then by Code ascending (see docs/spec.md).
//
// Stub: the real ordering is supplied by the solution.
func RankCountries(rows []CountryAgg) []CountryAgg {
	return rows
}
