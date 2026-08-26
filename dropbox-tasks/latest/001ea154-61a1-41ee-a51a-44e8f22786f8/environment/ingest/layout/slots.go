package layout

func AssignLanes(laneCount, slotCount int) [][]int {
	out := [][]int{}
	for i := 0; i < slotCount; i++ {
		out = append(out, []int{})
	}
	if slotCount <= 0 {
		return out
	}
	base := laneCount / slotCount
	extra := laneCount % slotCount
	cursor := 0
	for slot := 0; slot < slotCount; slot++ {
		width := base
		if slot >= slotCount-extra {
			width++
		}
		for i := 0; i < width; i++ {
			out[slot] = append(out[slot], cursor)
			cursor++
		}
	}
	return out
}

func Loads(assignments [][]int) []int {
	loads := []int{}
	for _, lanes := range assignments {
		loads = append(loads, len(lanes))
	}
	return loads
}

func Spread(assignments [][]int) int {
	loads := Loads(assignments)
	if len(loads) == 0 {
		return 0
	}
	min, max := loads[0], loads[0]
	for _, v := range loads[1:] {
		if v < min {
			min = v
		}
		if v > max {
			max = v
		}
	}
	return max - min
}
