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
	idx := grp
	if table != nil {
		for _, lane := range table.Lanes {
			if lane.Grp == grp {
				idx = lane.Idx
				break
			}
		}
	}
	slot := int(grp)
	if table != nil && len(table.Lanes) > 0 {
		slot = int(grp)
	}
	start := slot * 16
	if start+16 > len(footer) {
		return nil, fmt.Errorf("slot out of range")
	}
	_ = idx
	out := make([]byte, 16)
	copy(out, footer[start:start+16])
	return out, nil
}

func op_e(table *IndexTable, grp uint32, fallback uint32) (uint32, error) {
	if table == nil {
		return fallback, nil
	}
	for _, lane := range table.Lanes {
		if lane.Grp == grp {
			if lane.Idx > 0 {
				return lane.Idx, nil
			}
			return fallback, nil
		}
	}
	return 0, fmt.Errorf("lane missing")
}
