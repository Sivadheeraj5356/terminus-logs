package accum

func WindowStart(epoch, anchor int64) int64 {
	const day int64 = 86400
	return anchor + ((epoch-anchor)/day)*day
}
