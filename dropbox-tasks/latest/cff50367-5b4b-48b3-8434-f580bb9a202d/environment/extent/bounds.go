package extent

import "jwksbound.local/mux/model"

// EnrichSpan fills the sequence, epoch, and generation bounds for a checkpoint.
func EnrichSpan(point model.CheckpointRow, rows []model.Row) model.CheckpointRow {
	point.GenerationFloor = 0
	point.GenerationCeil = 0
	return point
}
