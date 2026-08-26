package fyn

import (
	"encoding/json"
	"os"
	"sort"

	"qxhub/pth"
)

type packKey struct {
	Kind   string
	Target string
	Mode   string
}

type shadowHint struct {
	Kind   string `json:"kind"`
	Match  string `json:"match"`
	Target string `json:"target"`
}

// cord_weft folds candidate rows into packed lanes for the active arm.
func cord_weft(rows []LaneRow, seq uint64) []LaneRow {
	type acc struct {
		row  LaneRow
		seen map[string]struct{}
	}
	var order []packKey
	packs := map[packKey]*acc{}
	admit := func(kind, target, want, mode string, matchers ...string) {
		k := packKey{Kind: kind, Target: target, Mode: mode}
		a, ok := packs[k]
		if !ok {
			a = &acc{
				row: LaneRow{
					Kind:   kind,
					Target: target,
					Want:   want,
					Mode:   mode,
					Seq:    seq,
				},
				seen: map[string]struct{}{},
			}
			packs[k] = a
			order = append(order, k)
		}
		for _, m := range matchers {
			if m == "" {
				continue
			}
			if _, hit := a.seen[m]; hit {
				continue
			}
			a.seen[m] = struct{}{}
			a.row.Match = append(a.row.Match, m)
		}
	}
	for _, r := range rows {
		if r.Want == "deny" {
			continue
		}
		admit(r.Kind, r.Target, r.Want, "always", r.Match...)
	}
	if raw, err := os.ReadFile(pth.LaneShadow()); err == nil {
		var h shadowHint
		if json.Unmarshal(raw, &h) == nil && h.Match != "" {
			admit(h.Kind, h.Target, "route", "always", h.Match)
		}
	}
	sort.SliceStable(order, func(i, j int) bool {
		if order[i].Kind != order[j].Kind {
			return order[i].Kind < order[j].Kind
		}
		return order[i].Target < order[j].Target
	})
	var out []LaneRow
	for _, k := range order {
		a := packs[k]
		sort.Strings(a.row.Match)
		out = append(out, a.row)
	}
	return out
}
