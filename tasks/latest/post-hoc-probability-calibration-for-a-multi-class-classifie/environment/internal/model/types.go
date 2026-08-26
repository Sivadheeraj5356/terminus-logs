// Package model holds the shared data structures for the plangen tool.
package model

import "encoding/json"

// Row is one labeled observation. Raw is an integer score in [0, Unit], Hit is
// 0 or 1, and Lane is a group index in [0, Lanes).
type Row struct {
	Raw  int `json:"raw"`
	Hit  int `json:"hit"`
	Lane int `json:"lane"`
}

// Rung is one shift stage of the ladder. Severity orders the ladder ascending.
// Budget is an integer bound in the same milli units as Unit.
// Span is the max allowed strength increase from the previous rung (default 2).
type Rung struct {
	Severity int   `json:"severity"`
	Budget   int   `json:"budget"`
	Span     int   `json:"span"`
	Rows     []Row `json:"rows"`
}

// UnmarshalJSON defaults a missing span to 2 so omission is not treated as zero.
func (r *Rung) UnmarshalJSON(data []byte) error {
	var aux struct {
		Severity int   `json:"severity"`
		Budget   int   `json:"budget"`
		Span     *int  `json:"span"`
		Rows     []Row `json:"rows"`
	}
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	r.Severity = aux.Severity
	r.Budget = aux.Budget
	r.Rows = aux.Rows
	if aux.Span == nil {
		r.Span = 2
	} else {
		r.Span = *aux.Span
	}
	return nil
}

// Bundle is a full ladder: a shared fit fold, an optional rim for edges, a
// holdout fold for emission witnesses, plus an ordered list of rungs.
type Bundle struct {
	Unit  int    `json:"unit"`
	Bins  int    `json:"bins"`
	Cells int    `json:"cells"`
	Lanes int    `json:"lanes"`
	Fit   []Row  `json:"fit"`
	Rim   []Row  `json:"rim"`
	Hold  []Row  `json:"hold"`
	Rungs []Rung `json:"rungs"`
}

// FamilyNames maps a strength index to its stable public name.
var FamilyNames = []string{"hist", "iso", "giso"}

// RungPlan is the emitted record for one rung.
type RungPlan struct {
	Severity  int   `json:"severity"`
	Family    string `json:"family"`
	Strength  int   `json:"strength"`
	Deviation int   `json:"deviation"`
	Allowance int   `json:"allowance"`
	Values    []int `json:"values"`
}

// HoldWitness reports each family's sealed-edge deviation on the hold fold.
type HoldWitness struct {
	Hist int `json:"hist"`
	Iso  int `json:"iso"`
	Giso int `json:"giso"`
}

// Plan is the emitted document for a full bundle.
type Plan struct {
	Unit  int         `json:"unit"`
	Bins  int         `json:"bins"`
	Hold  HoldWitness `json:"hold"`
	Rungs []RungPlan  `json:"rungs"`
}
