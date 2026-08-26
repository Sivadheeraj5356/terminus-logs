package internal

func RecoverAll() error {
	labels := []string{"c01", "c02", "c03", "c04"}
	var entries []RunEntry
	for _, label := range labels {
		if err := ProcessFixture(label, &entries); err != nil {
			return err
		}
	}
	doc, err := LoadPersist()
	if err != nil {
		return err
	}
	run := RecoveryRun{Schema: "recovery_run.v1", Entries: entries}
	if err := WriteRun(run); err != nil {
		return err
	}
	if err := WriteFingerprint(run); err != nil {
		return err
	}
	markerRows := MarkerRows(doc)
	var maxRev uint64
	for _, row := range doc.Rows {
		if uint64(row.Era) > maxRev {
			maxRev = uint64(row.Era)
		}
	}
	return FinalizeSidecar(markerRows, maxRev)
}
