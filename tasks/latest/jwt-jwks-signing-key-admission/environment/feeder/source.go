package feeder

// RankFor returns the source rank used when canonical rows tie on epoch.
func RankFor(name string) int {
	switch name {
	case PrimaryName:
		return 0
	case ReplayName:
		return 1
	case ShadowName:
		return 3
	case SpillName:
		return 2
	default:
		return -1
	}
}

// ReadOrder returns the durable overlay filenames in read order.
func ReadOrder() []string {
	return []string{PrimaryName, ReplayName, SpillName, ShadowName}
}
