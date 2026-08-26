package sim

import "chronctl/clock"

func wall_ns(sec int64, nsec int64, offsetMin int) int64 {
	return clock.UtcNs(sec, nsec, offsetMin)
}
