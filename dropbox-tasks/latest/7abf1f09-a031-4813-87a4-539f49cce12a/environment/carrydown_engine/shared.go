package main

import "sort"

func allocatePool(total int64, participants []string, weights map[string]int64) map[string]int64 {
	var wsum int64
	for _, p := range participants {
		w := weights[p]
		if w < 0 {
			w = 0
		}
		wsum += w
	}
	effWeights := make(map[string]int64, len(participants))
	if wsum == 0 {
		for _, p := range participants {
			effWeights[p] = 1
		}
		wsum = int64(len(participants))
	} else {
		for _, p := range participants {
			w := weights[p]
			if w < 0 {
				w = 0
			}
			effWeights[p] = w
		}
	}
	floors := make(map[string]int64, len(participants))
	rema := make(map[string]int64, len(participants))
	var allocated int64
	for _, p := range participants {
		num := total * effWeights[p]
		floors[p] = num / wsum
		rema[p] = num - floors[p]*wsum
		allocated += floors[p]
	}
	leftover := total - allocated
	order := make([]string, len(participants))
	copy(order, participants)
	sort.SliceStable(order, func(i, j int) bool {
		if rema[order[i]] != rema[order[j]] {
			return rema[order[i]] > rema[order[j]]
		}
		return order[i] < order[j]
	})
	for i := int64(0); i < leftover; i++ {
		floors[order[i]]++
	}
	return floors
}
