package fyn

// ApplyWeft is the public wrapper around cord_weft.
func ApplyWeft(rows []LaneRow, seq uint64) []LaneRow {
	return cord_weft(rows, seq)
}
