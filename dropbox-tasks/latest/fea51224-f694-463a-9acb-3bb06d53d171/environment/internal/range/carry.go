package rangepkg

import "slotmgr/internal/store"

func inherit_lane(cycle int, base int, prior []store.TranscriptRow) int {
	if cycle < 2 || len(prior) == 0 {
		return base
	}
	last := prior[len(prior)-1].LaneTick
	if last > base {
		return last
	}
	return base
}

func span_bytes(spans []Span) int {
	total := 0
	for _, s := range spans {
		total += s.End - s.Start
	}
	return total
}
