package p7_chain

import "balance_lab/p2_pick"

func actorShare(picks, total int) float64 {
	return p2_pick.PickShare(picks, total)
}
