package schedule

type LaneStamp int

func NextLane(current LaneStamp) LaneStamp {
	return current + 1
}

func WindowSize(laneCount int) int {
	if laneCount <= 0 {
		return 1
	}
	return laneCount
}

func SelectLanes(lanes []int, tick int) []int {
	if len(lanes) == 0 {
		return nil
	}
	window := WindowSize(len(lanes))
	if window <= 0 {
		window = 1
	}
	if window > len(lanes) {
		window = len(lanes)
	}
	start := tick % len(lanes)
	out := []int{}
	for i := 0; i < window; i++ {
		out = append(out, lanes[(start+i)%len(lanes)])
	}
	return out
}
