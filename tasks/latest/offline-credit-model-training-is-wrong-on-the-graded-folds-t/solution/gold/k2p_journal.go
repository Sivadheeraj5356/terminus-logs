package k2p

import (
	"encoding/json"
	"os"
	"path/filepath"

	"pitctl/hashx"
	"pitctl/types"
)

const Dir = "/app/output/.pit_journal"

func Persist(foldID string, report types.PitReport) error {
	if err := os.MkdirAll(Dir, 0o755); err != nil {
		return err
	}
	entry := types.JournalEntry{
		FoldID:       foldID,
		LedgerDigest: report.LedgerDigest,
		RowCount:     report.RowCount,
		SegDigests:   hashx.RowSegs(report.Rows),
	}
	b, err := json.MarshalIndent(entry, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(Dir, foldID+".json"), append(b, '\n'), 0o644)
}
