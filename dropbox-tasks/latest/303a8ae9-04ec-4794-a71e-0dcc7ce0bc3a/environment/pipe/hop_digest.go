package pipe

import (
	"pitctl/hashx"
	"pitctl/types"
)

func digestOf(foldID string, rows []types.RowOut) string {
	return hashx.LedgerDigest(foldID, rows)
}
