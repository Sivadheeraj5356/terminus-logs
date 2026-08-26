package pipe

import "pitctl/skew"

func effTime(tMs, wmMs, lagMs int64) int64 {
	return skew.EffectiveTime(tMs, wmMs, lagMs)
}
