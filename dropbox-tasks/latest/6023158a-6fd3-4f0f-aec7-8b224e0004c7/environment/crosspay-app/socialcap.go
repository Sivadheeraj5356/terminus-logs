package main

// This file defines the global employer social-contribution ceiling enforced
// once per `report` run. Unlike SocialParams and CountryFloor in contrib.go,
// this rule is not a per-region or per-country figure: it bounds the AGGREGATE
// employer social spend across every country in a single run, in the reporting
// base currency, and must be enforced before that spend is folded back into
// each country's employer cost total (see docs/spec.md).

// GlobalSocialCapBaseMicros is the fixed ceiling, in micro-units of the base
// currency, on the sum of every country's raw employer social-contribution
// subtotal for a report run, once each country's subtotal is independently
// converted to the base currency. It is an institutional constant.
const GlobalSocialCapBaseMicros int64 = 100000000

// CountrySocialSubtotal is one country's raw, pre-cap employer
// social-contribution subtotal (the sum of SocialContribution across every
// employee assigned there), in micro-units of that country's own currency.
type CountrySocialSubtotal struct {
	Code     string
	Currency string
	Local    int64
}

// ApplyGlobalSocialCap enforces GlobalSocialCapBaseMicros against a report run
// (see docs/spec.md for the exact apportionment and conversion rule). It
// returns each country's adjusted local social-contribution subtotal, keyed by
// country code.
//
// Stub: the real computation is supplied by the solution.
func ApplyGlobalSocialCap(subtotals []CountrySocialSubtotal) map[string]int64 {
	out := map[string]int64{}
	for _, s := range subtotals {
		out[s.Code] = s.Local
	}
	return out
}
