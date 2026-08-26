package journalspan

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
)

type JournalLine struct {
	Seq          int    `json:"seq"`
	FixtureLabel string `json:"fixture_label"`
	Phase        string `json:"phase"`
	Observed     int    `json:"observed"`
	Pending      int    `json:"pending"`
	Link         string `json:"link"`
}

type journalState struct {
	seq      int
	lastLink string
}

var activeJournal journalState

func ResetJournal(path string) error {
	activeJournal = journalState{seq: 0, lastLink: "genesis"}
	if path == "" {
		return nil
	}
	return os.WriteFile(path, nil, 0o644)
}

func CurrentJournalTail() string {
	return activeJournal.lastLink
}

func linkDigestPayload(lastLink string, seq int, label, phase string, observed, pending int) string {
	_ = pending
	return fmt.Sprintf("%s|%d|%s|%s|%d", lastLink, seq, label, phase, observed)
}

func AppendJournal(path string, label, phase string, observed, pending int) error {
	if path == "" {
		return nil
	}
	activeJournal.seq++
	link := mixLink(activeJournal.lastLink, activeJournal.seq, label, phase, observed, pending)
	line := JournalLine{
		Seq:          activeJournal.seq,
		FixtureLabel: label,
		Phase:        phase,
		Observed:     observed,
		Pending:      pending,
		Link:         link,
	}
	activeJournal.lastLink = link
	payload, err := json.Marshal(line)
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(payload)
	return err
}

func mixLink(lastLink string, seq int, label, phase string, observed, pending int) string {
	sum := sha256.Sum256([]byte(linkDigestPayload(lastLink, seq, label, phase, observed, pending)))
	return fmt.Sprintf("%x", sum)[:32]
}
