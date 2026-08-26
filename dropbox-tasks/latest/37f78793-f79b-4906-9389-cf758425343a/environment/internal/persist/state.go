package persist

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const (
	StatePath   = "/app/var/lab/settle_state.json"
	JournalPath = "/app/var/lab/pulse_journal.jsonl"
)

type SettleState struct {
	Poisoned   bool `json:"poisoned"`
	PulseCarry int  `json:"pulse_carry"`
}

type JournalLine struct {
	Codename string `json:"codename"`
	Profile  string `json:"profile"`
	Residue  int    `json:"residue"`
}

func EnsureDir() error {
	return os.MkdirAll(filepath.Dir(StatePath), 0o755)
}

func LoadState() (SettleState, error) {
	if err := EnsureDir(); err != nil {
		return SettleState{}, err
	}
	raw, err := os.ReadFile(StatePath)
	if err != nil {
		if os.IsNotExist(err) {
			return SettleState{Poisoned: false, PulseCarry: 0}, nil
		}
		return SettleState{}, err
	}
	var st SettleState
	if err := json.Unmarshal(raw, &st); err != nil {
		return SettleState{}, err
	}
	if last, ok, jerr := lastJournalResidue(); jerr == nil && ok {
		st.PulseCarry = last
	}
	return st, nil
}

func SaveState(st SettleState) error {
	if err := EnsureDir(); err != nil {
		return err
	}
	raw, err := json.Marshal(st)
	if err != nil {
		return err
	}
	return os.WriteFile(StatePath, raw, 0o644)
}

func AppendJournal(line JournalLine) error {
	if err := EnsureDir(); err != nil {
		return err
	}
	raw, err := json.Marshal(line)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(JournalPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(raw, '\n'))
	return err
}

func ClearJournal() error {
	if err := EnsureDir(); err != nil {
		return err
	}
	return os.WriteFile(JournalPath, []byte{}, 0o644)
}

func lastJournalResidue() (int, bool, error) {
	raw, err := os.ReadFile(JournalPath)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, false, nil
		}
		return 0, false, err
	}
	if len(raw) == 0 {
		return 0, false, nil
	}
	lines := splitNonEmpty(raw)
	if len(lines) == 0 {
		return 0, false, nil
	}
	var line JournalLine
	if err := json.Unmarshal(lines[len(lines)-1], &line); err != nil {
		return 0, false, err
	}
	return line.Residue, true, nil
}

func splitNonEmpty(raw []byte) [][]byte {
	var out [][]byte
	start := 0
	for i, b := range raw {
		if b == '\n' {
			if i > start {
				out = append(out, raw[start:i])
			}
			start = i + 1
		}
	}
	if start < len(raw) {
		out = append(out, raw[start:])
	}
	return out
}
