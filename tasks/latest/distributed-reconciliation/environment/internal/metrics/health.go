package metrics

// NodeUtilization returns peak fraction of nodes busy in any tick.
func NodeUtilization(peakBusy, nodeCount int) float64 {
	if nodeCount <= 0 {
		return 0
	}
	return float64(peakBusy) / float64(nodeCount)
}

// StallIndex estimates scheduler stall pressure from idle nodes vs queued jobs.
func StallIndex(idleNodes, queued int) float64 {
	if queued == 0 {
		return 0
	}
	return float64(idleNodes) / float64(queued+1)
}

// P95Wait computes the documented 95th percentile of positive queue waits.
func P95Wait(waits []int) int {
	positive := make([]int, 0, len(waits))
	for _, w := range waits {
		if w > 0 {
			positive = append(positive, w)
		}
	}
	if len(positive) == 0 {
		return 0
	}
	for i := 0; i < len(positive); i++ {
		for j := i + 1; j < len(positive); j++ {
			if positive[j] < positive[i] {
				positive[i], positive[j] = positive[j], positive[i]
			}
		}
	}
	idx := (len(positive)*95 + 99) / 100
	if idx >= len(positive) {
		idx = len(positive) - 1
	}
	return positive[idx]
}
