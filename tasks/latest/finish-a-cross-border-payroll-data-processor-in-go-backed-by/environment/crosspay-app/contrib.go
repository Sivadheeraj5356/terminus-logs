package main

// This file defines the fixed employer social-contribution parameters. Like the
// statutory withholding schedules in schedules.go, these are institutional
// constants that cannot be derived from anything else, so they are given here in
// full and documented in docs/spec.md. How they combine into a contribution
// figure (the clamp order, the rounding) is NOT spelled out here; that math is
// part of the task.

// SocialRule is one region's employer social-contribution rule: a single
// marginal RateBp in basis points charged on the contributory base, and a hard
// CapMicros ceiling on that base in micro-units of gross.
type SocialRule struct {
	RateBp    int64
	CapMicros int64
}

// SocialParams holds the social-contribution rule for each statutory region key.
// The region keys match the withholding schedule keys in schedules.go.
var SocialParams = map[string]SocialRule{
	"ASIA":     {RateBp: 900, CapMicros: 120000000},
	"EUROPE":   {RateBp: 1300, CapMicros: 100000000},
	"OCEANIA":  {RateBp: 1050, CapMicros: 90000000},
	"AMERICAS": {RateBp: 765, CapMicros: 130000000},
	"AFRICA":   {RateBp: 600, CapMicros: 80000000},
}

// CountryFloor holds the per-country floor on the contributory base, in
// micro-units of gross, keyed by ISO 3166-1 alpha-2 code. It raises the base to
// at least this figure before the region cap is applied.
var CountryFloor = map[string]int64{
	"JP": 20000000,
	"BH": 125000000,
	"KW": 15000000,
	"IN": 8000000,
	"DE": 25000000,
	"GB": 22000000,
	"SE": 24000000,
	"AU": 18000000,
	"FR": 25000000,
	"IT": 25000000,
	"ES": 25000000,
}
