package main

// This file defines the fixed cross-rate table used to convert a local amount to
// the reporting base currency. These are institutional constants, given here in
// full and documented in docs/spec.md. The conversion routine (how many legs,
// which rounding) is NOT spelled out here; that math is part of the task.

// BaseCurrency is the reporting currency every converted cost is expressed in.
const BaseCurrency = "USD"

// PivotCurrency is the intermediate currency all conversions route through. A
// local amount is never converted straight to the base; it is taken to the pivot
// first and then to the base.
const PivotCurrency = "XDR"

// PivotRate maps an ISO 4217 currency code to its value expressed in micro-units
// of the pivot currency per one whole major unit of that currency (so one whole
// USD is worth PivotRate["USD"] micro-XDR). The pivot's own rate is 1000000.
var PivotRate = map[string]int64{
	"USD": 752000,
	"XDR": 1000000,
	"JPY": 5100,
	"INR": 9050,
	"BHD": 1994000,
	"KWD": 2440000,
	"EUR": 815000,
	"GBP": 953000,
	"SEK": 71500,
	"AUD": 496000,
}
