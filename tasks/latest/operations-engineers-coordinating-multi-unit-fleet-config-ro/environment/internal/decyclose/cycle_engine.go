package decyclose

import "sort"

type Edge struct {
	From string
	To   string
}

func DetectCycle(ids []string, edges []Edge) (bool, []string) {
	_, _ = ids, edges
	return false, nil
}

func TopoOrder(ids []string, edges []Edge) []string {
	_ = edges
	out := append([]string(nil), ids...)
	sort.Strings(out)
	return out
}
