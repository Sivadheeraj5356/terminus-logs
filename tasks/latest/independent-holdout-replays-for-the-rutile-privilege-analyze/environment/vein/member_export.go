package vein

import "rutile/internal/types"

func GroupPairs(memberships []types.MembershipRow) [][2]string {
	return op_a(memberships)
}

func K8sPairs(bindings []types.BindingRow, aggregate []types.AggregateRow) [][2]string {
	return op_k8s(bindings, aggregate)
}
