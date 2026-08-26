package r7k

import "pitctl/types"

func Resolve(request string, table []types.RemapRow, atMs int64) string {
	cur := request
	seen := map[string]bool{cur: true}
	for hop := 0; hop < 8; hop++ {
		bestIdx := -1
		bestFrom := int64(-1)
		for i, row := range table {
			if row.Alias != cur {
				continue
			}
			if row.ActiveFromMs > atMs {
				continue
			}
			if row.ActiveFromMs > bestFrom || (row.ActiveFromMs == bestFrom && i > bestIdx) {
				bestFrom = row.ActiveFromMs
				bestIdx = i
			}
		}
		if bestIdx < 0 {
			return cur
		}
		next := table[bestIdx].Canonical
		if seen[next] {
			return request
		}
		seen[next] = true
		cur = next
	}
	return cur
}
