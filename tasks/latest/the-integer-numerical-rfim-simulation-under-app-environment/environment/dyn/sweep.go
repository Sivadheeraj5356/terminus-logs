package dyn

import "rfimhyst/internal/contract"

func nextTrigger(model *contract.RuntimeModel, states []int, current, target int64, direction int) (int64, bool) {
	var selected int64
	found := false
	for i, spin := range model.Spins {
		if direction == 1 && states[i] != -1 {
			continue
		}
		if direction == -1 && states[i] != 1 {
			continue
		}
		neighborTerm := int64(0)
		for _, edge := range model.Edges {
			if edge.A == i {
				neighborTerm += edge.CouplingMilli * int64(states[edge.B])
			} else if edge.B == i {
				neighborTerm += edge.CouplingMilli * int64(states[edge.A])
			}
		}
		threshold := -spin.BiasMilli - neighborTerm
		if direction == 1 {
			if threshold <= current || threshold > target {
				continue
			}
			if !found || threshold > selected {
				selected = threshold
				found = true
			}
		} else {
			if threshold >= current || threshold < target {
				continue
			}
			if !found || threshold < selected {
				selected = threshold
				found = true
			}
		}
	}
	return selected, found
}

func Traverse(model *contract.RuntimeModel, states []int, sample int, start, target int64, direction int) []contract.AvalancheRecord {
	current := start
	var records []contract.AvalancheRecord
	for event := 1; ; event++ {
		trigger, ok := nextTrigger(model, states, current, target, direction)
		if !ok {
			break
		}
		eventRecords := Stabilize(model, states, sample, event, trigger, direction)
		if len(eventRecords) == 0 {
			break
		}
		records = append(records, eventRecords...)
		current = trigger
	}
	return records
}
