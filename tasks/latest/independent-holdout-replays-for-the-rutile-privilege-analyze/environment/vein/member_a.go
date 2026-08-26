package vein

import (
	"rutile/internal/closure"
	"rutile/internal/types"
)

func op_a(memberships []types.MembershipRow) [][2]string {
	out := make([][2]string, 0)
	for _, row := range memberships {
		if !row.Active {
			continue
		}
		out = append(out, [2]string{row.From, row.To})
	}
	return out
}

func op_k8s(bindings []types.BindingRow, aggregate []types.AggregateRow) [][2]string {
	seed := make([][2]string, 0, len(bindings)+len(aggregate))
	for _, row := range bindings {
		seed = append(seed, [2]string{row.Subject, row.Role})
	}
	for _, row := range aggregate {
		seed = append(seed, [2]string{row.Role, row.Parent})
	}
	return closure.Expand(seed)
}
