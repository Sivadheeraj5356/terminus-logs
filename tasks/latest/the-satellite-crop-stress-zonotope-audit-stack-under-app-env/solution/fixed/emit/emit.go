package emit

import (
	"fmt"
	"hsdrive/internal/digest"
)

type Row struct {
	BindRef string `json:"bind_ref"`
	Body    string `json:"body"`
	RowID   int64  `json:"row_id"`
}

// Script seals a ledger row to sha256(bind_ref)[:8].
func Script(rowID uint64, binds map[uint64]string) (Row, error) {
	br, ok := binds[rowID]
	if !ok {
		return Row{}, fmt.Errorf("missing bind %d", rowID)
	}
	hx := digest.HexStr(br)
	if len(hx) < 8 {
		return Row{}, fmt.Errorf("short digest")
	}
	return Row{BindRef: br, Body: hx[:8], RowID: int64(rowID)}, nil
}
