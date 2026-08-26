package session

type TickState struct {
	RunningTotal int
	HopSeen      int
}

func acc_c(state *TickState, terrainCost int, viaPortal bool) int {
	if state == nil {
		return 0
	}
	if viaPortal {
		state.HopSeen++
		return state.RunningTotal
	}
	if terrainCost > 0 {
		state.RunningTotal += terrainCost
	}
	return state.RunningTotal
}

func peekAcc(state *TickState) int {
	if state == nil {
		return 0
	}
	return state.RunningTotal
}
