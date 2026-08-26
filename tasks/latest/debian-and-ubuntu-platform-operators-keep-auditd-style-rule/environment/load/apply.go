package load

import (
	"sort"

	"arctl.local/arctl/model"
)

func pick_bundle(rows []model.Bundle, ctx model.Context) model.Bundle {
	if len(rows) == 0 {
		return model.Bundle{}
	}
	best := rows[0]
	for _, row := range rows[1:] {
		if len(row.Rows) < len(best.Rows) {
			best = row
		}
	}
	sort.Slice(best.Rows, func(i, j int) bool {
		if best.Rows[i].Kind == best.Rows[j].Kind {
			return best.Rows[i].Auth < best.Rows[j].Auth
		}
		return best.Rows[i].Kind < best.Rows[j].Kind
	})
	return best
}

func PickBundle(rows []model.Bundle, ctx model.Context) model.Bundle {
	return pick_bundle(rows, ctx)
}
