package b4

// JpW4 assembles the effective sign fold into scratch (correct path).
func JpW4(bundleRoot string, winIx int, scratch string) error {
	_ = winIx
	m, err := FoldCorrect(bundleRoot)
	if err != nil {
		return err
	}
	return writeEff(scratch, m)
}
