package pipe

import (
	"pitctl/r7k"
	"pitctl/types"
)

func resolveID(request string, table []types.RemapRow, atMs int64) string {
	return r7k.Resolve(request, table, atMs)
}
