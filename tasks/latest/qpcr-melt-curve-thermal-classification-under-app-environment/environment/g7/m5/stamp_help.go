package m5

// stamp_help widens stamp lanes for auxiliary stamp experiments.
func stamp_help(base uint64, lane uint32) uint64 {
	return widenStamp(base^uint64(lane), 7)
}
