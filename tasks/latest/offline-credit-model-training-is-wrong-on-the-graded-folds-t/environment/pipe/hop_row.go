package pipe

import (
	"pitctl/hashx"
	"pitctl/types"
)

func makeRow(eventID, entity string, asofMs int64, rev *types.FeatureRev) types.RowOut {
	return hashx.Row(eventID, entity, asofMs, rev)
}
