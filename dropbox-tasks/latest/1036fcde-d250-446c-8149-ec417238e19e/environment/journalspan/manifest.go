package journalspan

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
)

type CompletionManifestLine struct {
	FixtureLabel string `json:"fixture_label"`
	JournalTail  string `json:"journal_tail"`
	TraceLines   int    `json:"trace_lines"`
	WaveChunks   int    `json:"wave_chunks"`
	CompletionSeal string `json:"completion_seal"`
}

func manifestDigestPayload(journalTail string, traceLines, waveSlices, observed int) string {
	return fmt.Sprintf("%s|%d|%d", journalTail, traceLines, observed)
}

func ComputeCompletionSeal(journalTail string, traceLines, waveSlices, observed int) string {
	sum := sha256.Sum256([]byte(manifestDigestPayload(journalTail, traceLines, waveSlices, observed)))
	return fmt.Sprintf("%x", sum)[:32]
}

func AppendCompletionManifest(path string, line CompletionManifestLine) error {
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

func ResetCompletionManifest(path string) error {
	if path == "" {
		return nil
	}
	return os.WriteFile(path, nil, 0o644)
}
