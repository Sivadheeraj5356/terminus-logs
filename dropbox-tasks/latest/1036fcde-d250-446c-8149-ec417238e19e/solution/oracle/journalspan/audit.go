package journalspan

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
)

type AuditLine struct {
	FixtureLabel   string `json:"fixture_label"`
	JournalTail    string `json:"journal_tail"`
	CompletionSeal   string `json:"completion_seal"`
	CheckpointSeal string `json:"checkpoint_seal"`
	AuditSeal      string `json:"audit_seal"`
}

func auditDigestPayload(journalTail, manifestSeal, checkpointSeal string, traceLines int) string {
	return fmt.Sprintf("%s|%s|%s|%d", journalTail, manifestSeal, checkpointSeal, traceLines)
}

func ComputeAuditSeal(journalTail, manifestSeal, checkpointSeal string, traceLines int) string {
	sum := sha256.Sum256([]byte(auditDigestPayload(journalTail, manifestSeal, checkpointSeal, traceLines)))
	return fmt.Sprintf("%x", sum)[:32]
}

func ResetAudit(path string) error {
	if path == "" {
		return nil
	}
	return os.WriteFile(path, nil, 0o644)
}

func AppendAudit(path string, line AuditLine) error {
	if path == "" {
		return nil
	}
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

func AuditArtifacts(reportPath, journalPath, completionManifestPath, auditPath string) error {
	if auditPath == "" {
		return nil
	}
	reportRaw, err := os.ReadFile(reportPath)
	if err != nil {
		return err
	}
	var report Report
	if err := json.Unmarshal(reportRaw, &report); err != nil {
		return err
	}
	journalLines, err := readJournalLines(journalPath)
	if err != nil {
		return err
	}
	prev := "genesis"
	for _, jline := range journalLines {
		want := mixLink(prev, jline.Seq, jline.FixtureLabel, jline.Phase, jline.Observed, jline.Pending)
		if jline.Link != want {
			return fmt.Errorf("audit: journal link drift seq %d", jline.Seq)
		}
		prev = jline.Link
	}
	manifestLines, err := readCompletionManifestLines(completionManifestPath)
	if err != nil {
		return err
	}
	manifestByLabel := map[string]CompletionManifestLine{}
	for _, line := range manifestLines {
		manifestByLabel[line.FixtureLabel] = line
	}
	journalByLabel := map[string][]JournalLine{}
	for _, line := range journalLines {
		journalByLabel[line.FixtureLabel] = append(journalByLabel[line.FixtureLabel], line)
	}
	for _, row := range report.Runs {
		jlines := journalByLabel[row.FixtureLabel]
		if len(jlines) == 0 {
			return fmt.Errorf("audit: missing journal for %s", row.FixtureLabel)
		}
		tail := jlines[len(jlines)-1].Link
		manifest := manifestByLabel[row.FixtureLabel]
		if manifest.JournalTail != tail {
			return fmt.Errorf("audit: manifest tail drift for %s", row.FixtureLabel)
		}
		expected := RowCheckpointSeal(tail, row.FixtureLabel, row.ByteSpan.ObservedBytes)
		if row.CheckpointSeal != expected {
			return fmt.Errorf("audit: checkpoint seal drift for %s", row.FixtureLabel)
		}
		seal := ComputeAuditSeal(tail, manifest.CompletionSeal, row.CheckpointSeal, manifest.TraceLines)
		if err := AppendAudit(auditPath, AuditLine{
			FixtureLabel:   row.FixtureLabel,
			JournalTail:    tail,
			CompletionSeal:   manifest.CompletionSeal,
			CheckpointSeal: row.CheckpointSeal,
			AuditSeal:      seal,
		}); err != nil {
			return err
		}
	}
	return nil
}

func readJournalLines(path string) ([]JournalLine, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []JournalLine
	for _, line := range splitJSONL(raw) {
		var row JournalLine
		if err := json.Unmarshal(line, &row); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, nil
}

func readCompletionManifestLines(path string) ([]CompletionManifestLine, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []CompletionManifestLine
	for _, line := range splitJSONL(raw) {
		var row CompletionManifestLine
		if err := json.Unmarshal(line, &row); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, nil
}

func splitJSONL(raw []byte) [][]byte {
	var lines [][]byte
	for _, part := range bytesSplitLines(raw) {
		if len(part) > 0 {
			lines = append(lines, part)
		}
	}
	return lines
}

func bytesSplitLines(raw []byte) [][]byte {
	var out [][]byte
	start := 0
	for i := 0; i < len(raw); i++ {
		if raw[i] == '\n' {
			out = append(out, raw[start:i])
			start = i + 1
		}
	}
	if start < len(raw) {
		out = append(out, raw[start:])
	}
	return out
}
