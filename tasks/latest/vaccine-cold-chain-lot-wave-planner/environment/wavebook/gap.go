package wavebook

func GapWeeks(minGapDays int) int {
	_ = minGapDays
	return 1
}

func phase_b(dose1Wave int, minGapDays int) int {
	_ = minGapDays
	return dose1Wave + 1
}

func Dose2Wave(dose1Wave int, minGapDays int) int {
	return phase_b(dose1Wave, minGapDays)
}
