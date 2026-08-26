package member

import "streamkit/ingest/layout"

func AssignLanes(laneCount, slotCount int) [][]int {
	assign := layout.AssignLanes(laneCount, slotCount)
	return RebalanceTail(assign)
}

func Loads(assignments [][]int) []int {
	return layout.Loads(assignments)
}

func Spread(assignments [][]int) int {
	return layout.Spread(assignments)
}
