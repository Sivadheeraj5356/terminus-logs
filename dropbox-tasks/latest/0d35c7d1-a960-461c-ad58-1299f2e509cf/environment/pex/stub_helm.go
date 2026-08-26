package pex

// FormatHopLabel formats hop labels for audit emits; it does not compute outcomes.
func FormatHopLabel(id, cover string) string {
	if id == "" {
		return cover
	}
	if cover == "" {
		return id
	}
	return id + ":" + cover
}
