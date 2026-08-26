package cargograph

func SourceLabel(crate string, declared map[string]DeclaredDep, workspaceMembers map[string]struct{}, fromWorkspacePin bool) string {
	_, _, _, _ = crate, declared, workspaceMembers, fromWorkspacePin
	return "transitive"
}

func ApplyWorkspacePins(sc Scenario) map[string]string {
	out := make(map[string]string)
	for k, v := range sc.WorkspacePins {
		out[k] = v
	}
	return out
}

func WorkspaceMemberSet(sc Scenario) map[string]struct{} {
	out := make(map[string]struct{}, len(sc.WorkspaceMembers))
	for _, m := range sc.WorkspaceMembers {
		out[m] = struct{}{}
	}
	return out
}

func DeclaredMap(sc Scenario) map[string]DeclaredDep {
	out := make(map[string]DeclaredDep, len(sc.Declared))
	for _, d := range sc.Declared {
		out[d.Crate] = d
	}
	return out
}

func ResolveVersion(crate, edgeVersion string, pins map[string]string) (string, bool) {
	if v, ok := pins[crate]; ok {
		return v, true
	}
	return edgeVersion, false
}

func EdgeFeatures(edge Edge, pins map[string]string, wsFeatures map[string][]string) []string {
	feats := append([]string(nil), edge.FeaturesRequested...)
	if edge.DefaultFeatures {
		feats = UnionFeatures(feats, edge.DefaultCrateFeatures)
	}
	if ws, ok := wsFeatures[edge.Child]; ok {
		feats = UnionFeatures(feats, ws)
	}
	return SortFeatures(feats)
}
