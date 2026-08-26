package main

func applyDiscounts(listSubtotal, creditAmount, commitmentRaw int64) (creditApplied, commitmentApplied, net int64) {
	return applyPrecedence(listSubtotal, creditAmount, commitmentRaw, []string{"credit", "commitment", "on_demand"})
}

func applyPrecedence(listSubtotal, creditAmount, commitmentRaw int64, precedence []string) (creditApplied, commitmentApplied, net int64) {
	running := listSubtotal
	for _, step := range precedence {
		switch step {
		case "credit":
			creditApplied = creditAmount
			if creditApplied > running {
				creditApplied = running
			}
			running -= creditApplied
		case "commitment":
			commitmentApplied = commitmentRaw
			if commitmentApplied > running {
				commitmentApplied = running
			}
			running -= commitmentApplied
		case "on_demand":
		}
	}
	net = running
	return
}
