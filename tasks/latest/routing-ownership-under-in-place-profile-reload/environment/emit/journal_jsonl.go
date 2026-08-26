package emit

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type JournalLine struct {
	Phase        string `json:"phase"`
	GenPlanned   uint64 `json:"gen_planned"`
	GenCommitted uint64 `json:"gen_committed"`
	Profile      string `json:"profile"`
}

func MakeJournalLine(phase string, planned, committed uint64, profile string) JournalLine {
	return JournalLine{
		Phase: phase, GenPlanned: planned, GenCommitted: committed, Profile: profile,
	}
}

func AppendJournal(outDir string, line JournalLine) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	path := filepath.Join(outDir, "reconfigure_journal.jsonl")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	raw, err := json.Marshal(line)
	if err != nil {
		return err
	}
	_, err = f.Write(append(raw, '\n'))
	return err
}

func ResetJournal(outDir string) error {
	path := filepath.Join(outDir, "reconfigure_journal.jsonl")
	_ = os.Remove(path)
	return nil
}
