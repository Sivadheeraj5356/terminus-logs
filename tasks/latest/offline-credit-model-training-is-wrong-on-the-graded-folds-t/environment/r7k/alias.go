package r7k

import "pitctl/types"

func Resolve(request string, table []types.RemapRow, atMs int64) string {
	_ = atMs
	for _, row := range table {
		if row.Alias == request {
			return row.Canonical
		}
	}
	return request
}
