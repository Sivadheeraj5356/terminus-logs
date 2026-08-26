package rangepkg

import "slotmgr/internal/store"

func DiffSpans(a, b []store.Span) []store.Span {
	out := make([]store.Span, 0)
	seen := map[int]bool{}
	for _, s := range a {
		seen[s.Start] = true
	}
	for _, s := range b {
		if !seen[s.Start] {
			out = append(out, s)
		}
	}
	return out
}

func InspectStride(rows []store.TranscriptRow, expect int) bool {
	for _, r := range rows {
		if r.StrideUnits != expect {
			return false
		}
	}
	return true
}
