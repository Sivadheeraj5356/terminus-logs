package sectorfold

func clampSector(sec int) int {
	if sec < 0 {
		return 0
	}
	if sec > 7 {
		return 7
	}
	return sec
}

// OpS maps a sector index through the diversion table.
func OpS(sec int, table map[int]string) string {
	idx := clampSector(sec + 1)
	if v, ok := table[idx]; ok {
		return v
	}
	return "L1"
}
