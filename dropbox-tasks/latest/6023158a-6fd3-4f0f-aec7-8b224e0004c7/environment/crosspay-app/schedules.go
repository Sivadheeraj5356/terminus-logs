package main

// This file defines the fixed statutory withholding schedules. The bracket
// numbers are institutional constants that cannot be derived from anything else,
// so they are given here in full and documented in docs/spec.md. Each schedule
// is a progressive set of tiers ordered by ascending Upto (in micro-units of
// gross); the tier with the largest Upto is open-ended and applies to all gross
// above the previous bound. RateBp is the marginal rate in basis points.
//
// How a country's region maps onto one of these schedules is NOT spelled out
// here; that mapping is part of the task.

// openEnded is the sentinel upper bound of the last (open-ended) tier.
const openEnded int64 = 1 << 62

// Schedules holds every statutory schedule keyed by its region name.
var Schedules = map[string][]Bracket{
	"ASIA": {
		{Upto: 10000000, RateBp: 500},
		{Upto: 50000000, RateBp: 1500},
		{Upto: 200000000, RateBp: 2500},
		{Upto: openEnded, RateBp: 3500},
	},
	"EUROPE": {
		{Upto: 12000000, RateBp: 800},
		{Upto: 40000000, RateBp: 2000},
		{Upto: 150000000, RateBp: 3000},
		{Upto: openEnded, RateBp: 4200},
	},
	"OCEANIA": {
		{Upto: 18000000, RateBp: 1000},
		{Upto: 60000000, RateBp: 2200},
		{Upto: openEnded, RateBp: 3700},
	},
	"AMERICAS": {
		{Upto: 11000000, RateBp: 1000},
		{Upto: 45000000, RateBp: 2400},
		{Upto: openEnded, RateBp: 3200},
	},
	"AFRICA": {
		{Upto: 9000000, RateBp: 700},
		{Upto: 35000000, RateBp: 1800},
		{Upto: openEnded, RateBp: 3000},
	},
}

// RegionKeys returns the schedule region names in ascending order.
func RegionKeys() []string {
	return []string{"AFRICA", "AMERICAS", "ASIA", "EUROPE", "OCEANIA"}
}
