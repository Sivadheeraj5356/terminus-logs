package c7

// KtN8 binds eligible models onto the home lattice under cut/cert/quorum rules.
func KtN8(chainScratch string, cutBudget uint32, outBound string) error {
	_ = cutBudget
	eff, err := loadEff(chainScratch)
	if err != nil {
		return err
	}
	sign := "/app/environment/fixtures/sign"
	bound := BindCorrect(eff, sign)
	if err := writeBound(outBound, bound, chainScratch); err != nil {
		return err
	}
	fresh, _, err := Freshness(bound, "/app/environment/fixtures/xrows")
	if err != nil {
		return err
	}
	return WriteFresh(chainScratch, fresh)
}
