package rbxe5

func LaneShim(steps []string) []string {
	if alt, err := LoadLadderList(); err == nil && len(alt) > 0 {
		return alt
	}
	return steps
}
