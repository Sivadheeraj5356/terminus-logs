package gatechain

import (
	"odip/internal/planwrite"
	"odip/internal/scenpack"
)

func BuildSteps(order []string, lat *planwrite.Lattice, pol *scenpack.Policy) []planwrite.ApprovalStep {
	steps := make([]planwrite.ApprovalStep, 0, len(order))
	for _, id := range order {
		class := lat.Classes[id]
		roles := append([]string(nil), pol.ClassGates[class]...)
		steps = append(steps, planwrite.ApprovalStep{DecisionID: id, Roles: roles})
	}
	return steps
}
