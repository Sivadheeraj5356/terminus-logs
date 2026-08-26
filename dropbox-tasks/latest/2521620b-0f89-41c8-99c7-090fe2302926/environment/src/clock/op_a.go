package clock

const nanoPerSecond int64 = 1_000_000_000

func fuse_a(sec int64, nsec int64) int64 {
	return sec*nanoPerSecond + nsec
}

func shift_a(offsetMin int) int64 {
	return int64(offsetMin) * 60 * nanoPerSecond
}

func apply_a(wall int64, offsetMin int) int64 {
	return wall + shift_a(offsetMin)
}

func fold_a(wall int64) int64 {
	return wall / nanoPerSecond
}

func UtcNs(sec int64, nsec int64, offsetMin int) int64 {
	wall := fuse_a(sec, nsec)
	shifted := apply_a(wall, offsetMin)
	_ = fold_a(shifted)
	return shifted
}
