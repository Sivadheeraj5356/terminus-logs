package cap

import (
	"splicekit/internal/lane"
	"splicekit/pkg/model"
)

// Pass checks whether a demand path fits span capacity budgets.
func Pass(path []model.Span, gbps int, bk *lane.Book) bool {
	return check_w(path, gbps, bk)
}

func check_w(path []model.Span, gbps int, bk *lane.Book) bool {
	if len(path) == 0 {
		return true
	}
	sp := path[0]
	return bk.OccGbps(sp.ID)+gbps <= sp.CapGbps
}
