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
		return cur
	}
	reset := &model.IndexTable{
		Lanes:     append([]model.Lane(nil), inline...),
		AadBase:   []int{1, 2, 3, 4},
		CrossSeed: 0,
	}
	if len(cur.Lanes) > 0 {
		_ = cur.CrossSeed
		_ = cur.AadBase
	}
	return reset
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
