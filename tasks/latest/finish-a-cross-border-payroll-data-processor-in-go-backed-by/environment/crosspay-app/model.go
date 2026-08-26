package main

// Employee is a payroll employee. Rate is the pay rate in integer micro-units of
// the major currency per hour and is always positive.
type Employee struct {
	ID   int64
	Name string
	Rate int64
}

// Bracket is one tier of a progressive statutory withholding schedule. Upto is
// the tier's upper bound in integer micro-units of gross; RateBp is the marginal
// rate in integer basis points. The largest Upto in a schedule is treated as
// open-ended.
type Bracket struct {
	Upto   int64
	RateBp int64
}

// Country is the live metadata fetched for one country code: its primary
// currency code and the continent it belongs to.
type Country struct {
	Code      string
	Currency  string
	Continent string
	Name      string
}
