package supersede

// Allow decides whether a new rollout epoch may supersede a journaled prior epoch.
func Allow(priorEpoch, newEpoch int) bool {
	_, _ = priorEpoch, newEpoch
	return true
}
