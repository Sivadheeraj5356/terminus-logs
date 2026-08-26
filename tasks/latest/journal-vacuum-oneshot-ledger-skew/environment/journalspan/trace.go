package journalspan

import (
	"encoding/json"
	"os"

	"burstverify/internal/spool"
)

type LedgerTraceLine struct {
	FixtureLabel  string `json:"fixture_label"`
	Phase         string `json:"phase"`
	Observed      int    `json:"observed"`
	Pending       int    `json:"pending"`
	WriterEpoch   string `json:"writer_epoch"`
	ReaderEpoch   string `json:"reader_epoch"`
	SpanMix       string `json:"span_mix"`
}

func SpanMixCheckpoint(writer, reader string, ledger spool.Ledger) string {
	span := ByteSpan{
		StartOffset:   ledger.StartOffset,
		EndOffset:     ledger.StartOffset + ledger.ObservedBytes,
		ObservedBytes: ledger.ObservedBytes,
	}
	return MixFingerprint(writer, reader, span)
}

func AppendTrace(path string, line LedgerTraceLine) error {
	if path == "" {
		return nil
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	payload, err := json.Marshal(line)
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	_, err = f.Write(payload)
	return err
}

func ResetTrace(path string) error {
	if path == "" {
		return nil
	}
	return os.WriteFile(path, nil, 0o644)
}
