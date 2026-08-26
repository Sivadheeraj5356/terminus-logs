package splice

import "github.com/lab/cvstack/internal/model"

func Knit(src, dst []model.MapRow) []model.MapRow {
	out := make([]model.MapRow, len(src))
	copy(out, src)
	return out
}
