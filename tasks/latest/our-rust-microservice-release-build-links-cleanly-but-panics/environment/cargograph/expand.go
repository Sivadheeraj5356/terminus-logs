package cargograph

func ExpandFeatureAliases(features []string, aliases map[string][]string) []string {
	_ = aliases
	return SortFeatures(features)
}
