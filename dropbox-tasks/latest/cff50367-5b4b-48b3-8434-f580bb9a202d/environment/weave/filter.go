package weave

import "jwksbound.local/mux/model"

// Eligible reports whether a row belongs to the active run and phase.
func Eligible(rec model.Row, ctx model.Context) bool {
	return rec.RunID == ctx.RunID && rec.Phase == ctx.Phase
}
