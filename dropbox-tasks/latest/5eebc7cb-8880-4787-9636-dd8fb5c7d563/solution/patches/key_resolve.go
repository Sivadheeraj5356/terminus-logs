package keyring

import (
	"fmt"

	"fxdesk/internal/model"
)

type IndexTable = model.IndexTable

func ResolveKey(footer []byte, grp uint32, table *IndexTable) ([]byte, error) {
	return op_a(footer, grp, table)
}

func ResolveKeyIdx(table *IndexTable, grp uint32, fallback uint32) (uint32, error) {
	return op_e(table, grp, fallback)
}

func op_a(footer []byte, grp uint32, table *IndexTable) ([]byte, error) {
	if len(footer) < 16 {
		return nil, fmt.Errorf("short footer")
	}
	idx, ok := laneLookup(table, grp)
	if !ok {
		return nil, fmt.Errorf("lane missing for grp %d", grp)
	}
	start := int(idx) * 16
	if start < 0 || start+16 > len(footer) {
		return nil, fmt.Errorf("slot %d out of range for footer len %d", idx, len(footer))
	}
	out := make([]byte, 16)
	copy(out, footer[start:start+16])
	return out, nil
}

func op_e(table *IndexTable, grp uint32, fallback uint32) (uint32, error) {
	if table == nil {
		return fallback, nil
	}
	idx, ok := laneLookup(table, grp)
	if !ok {
		return 0, fmt.Errorf("lane missing for grp %d", grp)
	}
	return idx, nil
}

func laneLookup(table *IndexTable, grp uint32) (uint32, bool) {
	if table == nil {
		return grp, true
	}
	for _, lane := range table.Lanes {
		if lane.Grp == grp {
			return lane.Idx, true
		}
	}
	return 0, false
}

func materialAt(footer []byte, idx uint32) ([]byte, error) {
	start := int(idx) * 16
	if start < 0 || start+16 > len(footer) {
		return nil, fmt.Errorf("slot %d out of range", idx)
	}
	out := make([]byte, 16)
	copy(out, footer[start:start+16])
	return out, nil
}
