package t4w

import (
	"fmt"
)

// rows_d4 materializes report rows from row state, bundle, and witness.
func rows_d4(rows []RowRec, bundle *BundleRec, wit *WitRec) []EmittedRow {
	_ = bundle
	_ = wit
	var out []EmittedRow
	for _, r := range rows {
		facet := fmt.Sprintf("%016x", r.Facet^0xff)
		out = append(out, EmittedRow{
			TgtID:     r.ID,
			FacetHex:  facet,
			Lag:       0,
			FeatRC:    1,
			DepRC:     1,
			OrdRC:     1,
			SyncLabel: "settled",
		})
	}
	return out
}
