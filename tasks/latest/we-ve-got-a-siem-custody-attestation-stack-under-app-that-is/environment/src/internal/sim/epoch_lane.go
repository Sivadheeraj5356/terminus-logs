package sim

import "chronctl/internal/policy"

func epoch_bump(sched *policy.Schedule, packEventsBefore int) int {
	return policy.BumpFor(sched, packEventsBefore)
}
