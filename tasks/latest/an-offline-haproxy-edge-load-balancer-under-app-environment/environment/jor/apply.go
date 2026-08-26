package jor

import "qxhub/fyn"

// ApplyTally is the public wrapper around gate_tally.
func ApplyTally(rows []fyn.LaneRow, cells []CellSpec, rowCap, groupCap int) ([]fyn.LaneRow, error) {
	return gate_tally(rows, cells, rowCap, groupCap)
}
