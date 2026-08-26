package cargograph

func OnRuntimeFeatureSet(crate ResolvedCrate, profile, profileMode, targetTriple string, tags FeatureTags) bool {
	if targetTriple != "any" {
		switch profileMode {
		case "host":
			if targetTriple != "host" && targetTriple != "any" {
				return false
			}
		case "target":
			if targetTriple != "target" && targetTriple != "any" {
				return false
			}
		}
	}
	_ = crate
	_ = profile
	_ = tags
	return true
}

func FilterRuntimeFeatures(features []string, profile string, tags FeatureTags) []string {
	_, _ = profile, tags
	return SortFeatures(features)
}

func CrateOnRuntimeSet(crate ResolvedCrate, edgeTarget string, profileMode string) bool {
	switch profileMode {
	case "host":
		return edgeTarget == "host" || edgeTarget == "any"
	case "target":
		return edgeTarget == "target" || edgeTarget == "any"
	default:
		return true
	}
}
