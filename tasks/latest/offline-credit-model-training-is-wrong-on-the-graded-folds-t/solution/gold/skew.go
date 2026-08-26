package skew

func EffectiveTime(tMs, wmMs, lagMs int64) int64 {
	_, _ = wmMs, lagMs
	return tMs
}
