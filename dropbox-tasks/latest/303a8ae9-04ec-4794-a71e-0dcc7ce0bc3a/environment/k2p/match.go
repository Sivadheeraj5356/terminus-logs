package k2p

import (
	"pitctl/hashx"
	"pitctl/types"
)

func Match(foldID string, report types.PitReport, entry types.JournalEntry) (bool, string) {
	wantSegs := hashx.RowSegs(report.Rows)
	recon := hashx.LedgerFromSegs(foldID, entry.SegDigests)
	ok := entry.FoldID == foldID &&
		entry.LedgerDigest == report.LedgerDigest &&
		entry.RowCount == report.RowCount &&
		recon == report.LedgerDigest &&
		segEq(entry.SegDigests, wantSegs)
	if !ok {
		return false, "journal_mismatch"
	}
	return true, "match"
}

func segEq(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
