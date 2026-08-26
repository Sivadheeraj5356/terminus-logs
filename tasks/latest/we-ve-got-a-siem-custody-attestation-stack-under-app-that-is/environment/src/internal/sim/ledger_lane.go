package sim

import "chronctl/ledger"

func rebalance(leftBase int, rightBase int, leftCount int, rightCount int) (int, bool) {
	return ledger.Plan(leftBase, rightBase, leftCount, rightCount)
}
