package emit

import (
	"fmt"
	"hsdrive/internal/digest"
	"strconv"
)

type Row struct {
	BindRef string `json:"bind_ref"`
	Body    string `json:"body"`
	RowID   int64  `json:"row_id"`
}

// Script emits one ledger-bound script_rows record.
func Script(rowID uint64, binds map[uint64]string) (Row, error) {
	br, ok := binds[rowID]
	if !ok {
		return Row{}, fmt.Errorf("missing bind %d", rowID)
	}
	hx := digest.HexStr(strconv.FormatUint(rowID, 10))
	if len(hx) < 8 {
		return Row{}, fmt.Errorf("short digest")
	}
	return Row{BindRef: br, Body: hx[:8], RowID: int64(rowID)}, nil
}
