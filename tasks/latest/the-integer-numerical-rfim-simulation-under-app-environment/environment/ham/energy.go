package ham

import "rfimhyst/internal/contract"

func EnergyMilli(model *contract.RuntimeModel, states []int, external int64) int64 {
	var spinSum int64
	var biasTerm int64
	for i, spin := range model.Spins {
		spinSum += int64(states[i])
		biasTerm += spin.BiasMilli * int64(states[i])
	}
	var edgeTerm int64
	for _, edge := range model.Edges {
		edgeTerm += edge.CouplingMilli * int64(states[edge.A]*states[edge.B])
	}
	return -external*spinSum - biasTerm - edgeTerm
}

func MagnetizationSum(states []int) int {
	total := 0
	for _, state := range states {
		total += state
	}
	return total
}
