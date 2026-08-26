package pipe

import (
	"pitctl/k2p"
	"pitctl/types"
)

func saveJournal(foldID string, report types.PitReport) error {
	return k2p.Persist(foldID, report)
}

func readJournal(foldID string) (types.JournalEntry, error) {
	return k2p.Read(foldID)
}

func matchJournal(foldID string, report types.PitReport, entry types.JournalEntry) (bool, string) {
	return k2p.Match(foldID, report, entry)
}
