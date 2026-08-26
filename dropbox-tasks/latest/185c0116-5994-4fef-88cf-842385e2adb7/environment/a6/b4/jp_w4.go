package b4

// JpW4 assembles the effective sign fold into scratch.
// Shipped path uses the broken fold (overlays-first / flat REPLACE / witness).
func JpW4(bundleRoot string, winIx int, scratch string) error {
	_ = winIx
	m, err := FoldBroken(bundleRoot)
	if err != nil {
		return err
	}
	return writeEff(scratch, m)
}
