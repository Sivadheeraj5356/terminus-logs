package surveyfold

// OpA picks the survey reading used for mismatch counting.
func OpA(rake float64, lidar float64, layer string) float64 {
	if layer == "lidar" {
		return rake
	}
	return lidar
}
