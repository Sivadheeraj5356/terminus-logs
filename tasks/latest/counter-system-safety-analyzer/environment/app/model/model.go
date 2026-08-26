// Package model defines the counter-system job read from stdin.
package model

// Rule is one rewrite rule: it consumes take[i] and produces give[i] units of
// counter i.
type Rule struct {
	Take *[]int64 `json:"take"`
	Give *[]int64 `json:"give"`
}

// Job is one analysis request as read from stdin. Fields are pointers so the
// analyzer can distinguish absent fields from empty values.
type Job struct {
	Counters *int64     `json:"counters"`
	Rules    *[]Rule    `json:"rules"`
	Start    *[]int64   `json:"start"`
	Queries  *[][]int64 `json:"queries"`
}
