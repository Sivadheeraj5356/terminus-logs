package journalspan

import "burstverify/internal/spool"

type ReportRow struct {
	FixtureLabel   string   `json:"fixture_label"`
	WriterEpoch    string   `json:"writer_epoch"`
	ReaderEpoch    string   `json:"reader_epoch"`
	ByteSpan       ByteSpan `json:"byte_span"`
	Fingerprint    string   `json:"fingerprint"`
	CheckpointSeal string   `json:"checkpoint_seal"`
}

func BuildRecord(label, writer, reader string, ledger spool.Ledger) ReportRow {
	span := ByteSpan{
		StartOffset:   ledger.StartOffset,
		EndOffset:     ledger.StartOffset + ledger.ObservedBytes,
		ObservedBytes: ledger.ObservedBytes,
	}
	return ReportRow{
		FixtureLabel: label,
		WriterEpoch:  writer,
		ReaderEpoch:  reader,
		ByteSpan:     span,
		Fingerprint:  MixFingerprint(writer, reader, span),
	}
}

func BuildRecordWithSeal(label, writer, reader string, ledger spool.Ledger, journalTail string) ReportRow {
	row := BuildRecord(label, writer, reader, ledger)
	row.CheckpointSeal = RowCheckpointSeal(journalTail, label, ledger.ObservedBytes)
	return row
}
