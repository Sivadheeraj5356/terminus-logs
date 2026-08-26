package dyn

import (
	"rfimhyst/ham"
	"rfimhyst/internal/artifact"
	"rfimhyst/internal/contract"
)

func localForces(model *contract.RuntimeModel, states []int, external int64) []int64 {
	forces := make([]int64, len(model.Spins))
	for i, spin := range model.Spins {
		forces[i] = external + spin.BiasMilli
	}
	for _, edge := range model.Edges {
		forces[edge.A] += edge.CouplingMilli * int64(states[edge.B])
		forces[edge.B] += edge.CouplingMilli * int64(states[edge.A])
	}
	return forces
}

func Stabilize(model *contract.RuntimeModel, states []int, sample, event int, external int64, direction int) []contract.AvalancheRecord {
	var records []contract.AvalancheRecord
	for round := 1; ; round++ {
		forces := localForces(model, states, external)
		eligible := make([]int, 0)
		for i, state := range states {
			if direction == 1 && state == -1 && forces[i] >= 0 {
				eligible = append(eligible, i)
			}
			if direction == -1 && state == 1 && forces[i] <= 0 {
				eligible = append(eligible, i)
			}
		}
		if len(eligible) == 0 {
			break
		}
		beforeDigest := artifact.StateDigest(model, states)
		beforeEnergy := ham.EnergyMilli(model, states, external)
		flipped := make([]string, len(eligible))
		for i, index := range eligible {
			states[index] = -states[index]
			flipped[i] = model.Spins[index].ID
		}
		records = append(records, contract.AvalancheRecord{
			Sample:               sample,
			Event:                event,
			Round:                round,
			Direction:            direction,
			TriggerExternalMilli: external,
			Flipped:              flipped,
			BeforeDigest:         beforeDigest,
			AfterDigest:          artifact.StateDigest(model, states),
			EnergyBeforeMilli:    beforeEnergy,
			EnergyAfterMilli:     ham.EnergyMilli(model, states, external),
		})
	}
	return records
}
