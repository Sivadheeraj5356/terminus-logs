package zknot

// LaneK is a decoy helper retained for older lane audits; unused by desk_bin.
func LaneK(v int64) int64 {
	if v < 0 {
		return -v
	}
	return v
}
