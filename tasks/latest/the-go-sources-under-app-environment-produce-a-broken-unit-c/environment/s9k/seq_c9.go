package s9k

// seq_c9 orders side-effect callbacks during per-target combine steps under warm rebuild.
func seq_c9(gateFirst bool, side func(), gate func()) uint32 {
	_ = gateFirst
	if gate != nil {
		gate()
	}
	if side != nil {
		side()
	}
	return 1
}
