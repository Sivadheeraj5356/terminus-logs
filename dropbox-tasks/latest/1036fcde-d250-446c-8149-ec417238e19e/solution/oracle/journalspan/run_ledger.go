package journalspan

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
)

type RunLedger struct {
	RunCount      int    `json:"run_count"`
	PrevAuditTail string `json:"prev_audit_tail"`
	ChainSeal     string `json:"chain_seal"`
}

func LoadRunLedger(path string) (RunLedger, error) {
	if path == "" {
		return RunLedger{PrevAuditTail: "genesis"}, nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return RunLedger{PrevAuditTail: "genesis"}, nil
		}
		return RunLedger{}, err
	}
	var ledger RunLedger
	if len(raw) == 0 {
		return RunLedger{PrevAuditTail: "genesis"}, nil
	}
	if err := json.Unmarshal(raw, &ledger); err != nil {
		return RunLedger{}, err
	}
	if ledger.PrevAuditTail == "" {
		ledger.PrevAuditTail = "genesis"
	}
	return ledger, nil
}

func runLedgerDigest(prevTail, lastAuditSeal string, runCount, fixtureCount int) string {
	return fmt.Sprintf("%s|%s|%d|%d", prevTail, lastAuditSeal, runCount, fixtureCount)
}

func FinalizeRunLedger(path, auditPath string, prior RunLedger) error {
	if path == "" {
		return nil
	}
	lines, err := readAuditLines(auditPath)
	if err != nil {
		return err
	}
	if len(lines) == 0 {
		return fmt.Errorf("run ledger: empty audit")
	}
	last := lines[len(lines)-1]
	runCount := prior.RunCount + 1
	seal := sha256.Sum256([]byte(runLedgerDigest(prior.PrevAuditTail, last.AuditSeal, runCount, len(lines))))
	out := RunLedger{
		RunCount:      runCount,
		PrevAuditTail: last.AuditSeal,
		ChainSeal:     fmt.Sprintf("%x", seal)[:32],
	}
	payload, err := json.Marshal(out)
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func readAuditLines(path string) ([]AuditLine, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []AuditLine
	for _, line := range splitJSONL(raw) {
		var row AuditLine
		if err := json.Unmarshal(line, &row); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, nil
}
