package mica

import "rutile/internal/types"

func EntryNodes(identities []types.IdentityRow) map[string]struct{} {
	return op_d(identities)
}

func PathRows(entries, crowns map[string]struct{}, adj map[string][]string) []types.ChainRow {
	return op_h(entries, crowns, adj)
}
