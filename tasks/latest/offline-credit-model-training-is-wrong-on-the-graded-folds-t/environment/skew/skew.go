package skew

func EffectiveTime(tMs, wmMs, lagMs int64) int64 {
	_ = lagMs
	if tMs > wmMs {
		return tMs - wmMs
	}
	return tMs
}
