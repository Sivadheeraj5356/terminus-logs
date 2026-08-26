package tools

import "jwksbound.local/mux/model"

// CountRows returns the number of rows in a slice. Read-only diagnostics tool
// used by ad-hoc tooling; it does not participate in the audit pipeline.
func CountRows(rows []model.Row) int {
	return len(rows)
}
