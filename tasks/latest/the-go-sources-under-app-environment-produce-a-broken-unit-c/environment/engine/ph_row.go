package engine

import "ucg.local/workspace/t4w"

func EmitRows(rows []t4w.RowRec, bundle *t4w.BundleRec, wit *t4w.WitRec) []t4w.EmittedRow {
	return t4w.Emit(rows, bundle, wit)
}
