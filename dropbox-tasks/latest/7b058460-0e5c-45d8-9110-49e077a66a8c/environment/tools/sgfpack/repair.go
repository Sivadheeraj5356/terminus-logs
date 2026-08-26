package main

import (
	"fmt"
	"strings"
)

func repairArchive(root string) error {
	rows, _, _, errs := validateCurrent(root)
	if len(errs) > 0 {
		return fmt.Errorf(strings.Join(errs, "\n"))
	}
	entries := make([]RepairEntry, 0, len(rows))
	for _, row := range rows {
		entries = append(entries, RepairEntry{GameID: row.GameID, Result: row.Result, Reason: row.Reason})
	}
	return writeRepairState(root, entries)
}
