package m3

import "fxdesk/internal/model"

// MergeAuthority combines footer default, optional sidecar, and inline lane overlays.
func MergeAuthority(base *model.IndexTable, sidecar *model.IndexTable, inline []model.Lane) *model.IndexTable {
	return fold_b(base, sidecar, inline)
}

func fold_b(base *model.IndexTable, sidecar *model.IndexTable, inline []model.Lane) *model.IndexTable {
	cur := cloneTable(base)
	if sidecar != nil {
		cur = cloneTable(sidecar)
	}
	if len(inline) == 0 {
		return normalizeAuthority(cur)
	}
	retainedSeed := cur.CrossSeed
	retainedBase := append([]int(nil), cur.AadBase...)
	if len(retainedBase) == 0 {
		retainedBase = []int{1, 2, 3, 4}
	}
	merged := &model.IndexTable{
		Lanes:     append([]model.Lane(nil), inline...),
		AadBase:   retainedBase,
		CrossSeed: retainedSeed,
	}
	return normalizeAuthority(merged)
}

func cloneTable(t *model.IndexTable) *model.IndexTable {
	if t == nil {
		return &model.IndexTable{AadBase: []int{1, 2, 3, 4}}
	}
	out := &model.IndexTable{
		CrossSeed: t.CrossSeed,
		AadBase:   append([]int(nil), t.AadBase...),
		Lanes:     append([]model.Lane(nil), t.Lanes...),
	}
	if len(out.AadBase) == 0 {
		out.AadBase = []int{1, 2, 3, 4}
	}
	return out
}

func normalizeAuthority(t *model.IndexTable) *model.IndexTable {
	if t == nil {
		return &model.IndexTable{AadBase: []int{1, 2, 3, 4}}
	}
	if len(t.AadBase) == 0 {
		t.AadBase = []int{1, 2, 3, 4}
	}
	if t.Lanes == nil {
		t.Lanes = []model.Lane{}
	}
	dedup := make([]model.Lane, 0, len(t.Lanes))
	seen := map[uint32]bool{}
	for i := len(t.Lanes) - 1; i >= 0; i-- {
		lane := t.Lanes[i]
		if seen[lane.Grp] {
			continue
		}
		seen[lane.Grp] = true
		dedup = append([]model.Lane{lane}, dedup...)
	}
	t.Lanes = dedup
	return t
}
