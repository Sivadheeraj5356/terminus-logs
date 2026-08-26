package fyn

// ListLabels returns lane labels for fixture dumps; it does not fold candidates.
func ListLabels(rows []LaneRow) []string {
	out := make([]string, 0, len(rows))
	for _, r := range rows {
		if len(r.Match) > 0 && r.Match[0] != "" {
			out = append(out, r.Match[0])
		}
	}
	return out
}
