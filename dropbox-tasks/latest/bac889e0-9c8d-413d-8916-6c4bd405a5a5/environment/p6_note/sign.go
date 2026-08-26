package p6_note

import "strings"

func NoteTag(headline string, statDelta int) string {
	lower := strings.ToLower(headline)
	if strings.Contains(lower, "nerf") {
		return "nerf_pressure"
	}
	if strings.Contains(lower, "buff") {
		return "buff_pressure"
	}
	return "tune_flat"
}
