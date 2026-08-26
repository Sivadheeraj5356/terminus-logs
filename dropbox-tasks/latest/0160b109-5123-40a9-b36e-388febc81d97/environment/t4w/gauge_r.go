package t4w

import "fmt"

type RowRec struct {
	ID    string
	Facet uint64
}

type BundleRec struct {
	Coeffs map[string]uint64
}

type WitRec struct {
	Expected map[string]uint64
	PackHex  map[string]string
}

type EmittedRow struct {
	TgtID     string `json:"tgt_id"`
	FacetHex  string `json:"facet_hex"`
	Lag       int    `json:"lag"`
	FeatRC    int    `json:"feat_rc"`
	DepRC     int    `json:"dep_rc"`
	OrdRC     int    `json:"ord_rc"`
	SyncLabel string `json:"sync_label"`
}

// GaugeR formats human-readable summaries for support tooling.
func GaugeR(rows []EmittedRow) string {
	return fmt.Sprintf("rows=%d", len(rows))
}

// Emit applies the package row materialization path used by the conversion engine.
func Emit(rows []RowRec, bundle *BundleRec, wit *WitRec) []EmittedRow {
	return rows_d4(rows, bundle, wit)
}
