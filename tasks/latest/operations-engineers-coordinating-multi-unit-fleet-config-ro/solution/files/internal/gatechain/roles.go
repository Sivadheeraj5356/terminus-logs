package gatechain

import (
	"odip/internal/planwrite"
	"odip/internal/scenpack"
)

func BuildSteps(order []string, lat *planwrite.Lattice, pol *scenpack.Policy) []planwrite.ApprovalStep {
	scoreByID := map[string]int{}
	for _, row := range lat.ImpactRows {
		scoreByID[row.DecisionID] = row.ImpactScore
	}
	steps := make([]planwrite.ApprovalStep, 0, len(order))
	for _, id := range order {
		class := lat.Classes[id]
		roles := append([]string(nil), pol.ClassGates[class]...)
		score := scoreByID[id]
		for _, th := range pol.ScoreThresholds {
			if score >= th.MinScore {
				roles = appendUnique(roles, th.ExtraRoles...)
			}
		}
		flags := lat.Flags[id]
		for _, f := range flags {
			if f == pol.Conditional.ExceptionFlag {
				roles = appendUnique(roles, pol.Conditional.ExtraRole)
			}
		}
		steps = append(steps, planwrite.ApprovalStep{DecisionID: id, Roles: roles})
	}
	return steps
}

func appendUnique(dst []string, extras ...string) []string {
	seen := map[string]bool{}
	for _, r := range dst {
		seen[r] = true
	}
	for _, e := range extras {
		if !seen[e] {
			dst = append(dst, e)
			seen[e] = true
		}
	}
	return dst
}
