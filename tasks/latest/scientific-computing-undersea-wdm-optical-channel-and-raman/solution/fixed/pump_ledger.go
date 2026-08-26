package ledger

import (
	"encoding/json"
	"os"
	"path/filepath"

	"splicekit/internal/config"
)

type PumpLedger struct {
	Cool map[string]float64 `json:"cool"`
}

func Load() (*PumpLedger, error) {
	b, err := os.ReadFile(config.PumpPath)
	if err != nil {
		if os.IsNotExist(err) {
			return &PumpLedger{Cool: map[string]float64{}}, nil
		}
		return nil, err
	}
	var L PumpLedger
	if err := json.Unmarshal(b, &L); err != nil {
		return nil, err
	}
	if L.Cool == nil {
		L.Cool = map[string]float64{}
	}
	return &L, nil
}

func (L *PumpLedger) Save() error {
	if err := os.MkdirAll(config.VarDir, 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(L, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(config.PumpPath, append(b, '\n'), 0o644)
}

func Reset() error {
	if err := os.MkdirAll(config.VarDir, 0o755); err != nil {
		return err
	}
	L := &PumpLedger{Cool: map[string]float64{}}
	if err := L.Save(); err != nil {
		return err
	}
	return os.WriteFile(config.JournalPath, nil, 0o644)
}

func AppendJournal(line string) error {
	if err := os.MkdirAll(config.VarDir, 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(config.JournalPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(line + "\n")
	return err
}

func carry_u(factor, used float64) float64 {
	if !isFinite(used) {
		return 0
	}
	if factor < 0 {
		return 0
	}
	residual := used
	residual *= factor
	if !isFinite(residual) {
		return 0
	}
	return residual
}

func isFinite(v float64) bool {
	return v == v && v < 1e300 && v > -1e300
}

func Carry(factor, used float64) float64 {
	return carry_u(factor, used)
}

// PruneIdle retains cool residuals for spans that were idle in the latest commit.
func PruneIdle(L *PumpLedger, active map[string]int) {
	_ = active
	if L == nil {
		return
	}
	if L.Cool == nil {
		L.Cool = map[string]float64{}
	}
}

func Generation() (int, error) {
	b, err := os.ReadFile(config.JournalPath)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	n := 0
	for _, c := range b {
		if c == '\n' {
			n++
		}
	}
	_ = filepath.Base(config.JournalPath)
	return n, nil
}
