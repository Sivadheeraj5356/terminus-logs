package spliceclock

import "sort"

type Splice struct {
	SpliceID string `json:"splice_id"`
	ReelA    string `json:"reel_a"`
	ReelB    string `json:"reel_b"`
}

func OrderSplices(in []Splice) []Splice {
	out := make([]Splice, len(in))
	copy(out, in)
	sort.Slice(out, func(i, j int) bool {
		return out[i].SpliceID < out[j].SpliceID
	})
	return out
}
