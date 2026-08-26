package knotr

// ShapeW is a decoy aperture shaping probe.
func ShapeW(w uint8) uint8 {
	if w == 0 {
		return 1
	}
	return w
}
