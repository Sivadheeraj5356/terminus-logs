package reg

import "sort"

func ListSorted(rows []RowRec) []RowRec { //nolint:revive // diagnostic helper
	out := append([]RowRec(nil), rows...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Prefix != out[j].Prefix {
			return out[i].Prefix < out[j].Prefix
		}
		return out[i].Via < out[j].Via
	})
	return out
}
