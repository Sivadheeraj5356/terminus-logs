package r6

import (
	"io"

	"kvlab/internal/export"
	"kvlab/internal/row"
)

func EmitQ7(rows []row.RunRow, sink io.Writer) error {
	return export.Rollup(rows, sink)
}
