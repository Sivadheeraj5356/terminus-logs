package sim

import "chronctl/rank"

func rank_ticket(wall int64, anchor int, segID int, seq int) string {
	return rank.KeyBlob(wall, anchor, segID, seq)
}
