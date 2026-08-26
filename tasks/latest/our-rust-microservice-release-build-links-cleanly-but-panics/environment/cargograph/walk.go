package cargograph

import "sort"

func declaredProcessingOrder(sc Scenario) []DeclaredDep {
	out := append([]DeclaredDep(nil), sc.Declared...)
	sort.Slice(out, func(i, j int) bool {
		return out[i].Crate < out[j].Crate
	})
	return out
}

type walkResult struct {
	crates             map[string]ResolvedCrate
	crateTargets       map[string]string
	conflicts          map[string]FeatureConflict
	edgesTraversed     int
	framesRejected     int
	truncatedTail      int
	conflictRowsPurged int
}

type winnerState struct {
	version    string
	depth      int
	parentKey  string
	crateKey   string
	source     string
	features   []string
}

func depthCap(sc Scenario) int {
	if sc.TraversalDepthCap > 0 {
		return sc.TraversalDepthCap
	}
	return 64
}

func exclusionSet(sc Scenario) map[string]struct{} {
	out := make(map[string]struct{}, len(sc.Exclusions))
	for _, e := range sc.Exclusions {
		out[e] = struct{}{}
	}
	return out
}

func sortEdges(edges []Edge) []Edge {
	out := append([]Edge(nil), edges...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].EdgeID != out[j].EdgeID {
			return out[i].EdgeID < out[j].EdgeID
		}
		return out[i].Child < out[j].Child
	})
	return out
}

func resolveGraph(sc Scenario, edges []Edge, pins map[string]string, wsFeatures map[string][]string, declared map[string]DeclaredDep, members map[string]struct{}, exclusions map[string]struct{}, record bool) walkResult {
	edgesByParent := make(map[string][]Edge)
	for _, e := range edges {
		edgesByParent[e.Parent] = append(edgesByParent[e.Parent], e)
	}
	for p := range edgesByParent {
		edgesByParent[p] = sortEdges(edgesByParent[p])
	}

	winners := make(map[string]*winnerState)
	res := walkResult{
		crates:       make(map[string]ResolvedCrate),
		crateTargets: make(map[string]string),
		conflicts:    make(map[string]FeatureConflict),
	}
	cap := depthCap(sc)

	addRejected := func(crate, selected, rejected string) {
		if !record || rejected == selected {
			return
		}
		key := crate + "\x00" + selected
		c, ok := res.conflicts[key]
		if !ok {
			c = FeatureConflict{
				Crate:            crate,
				SelectedVersion:  selected,
				RejectedVersions: []string{},
				ResolutionReason: "nearest",
				Severity:         "soft",
			}
		}
		found := false
		for _, r := range c.RejectedVersions {
			if r == rejected {
				found = true
				break
			}
		}
		if !found {
			c.RejectedVersions = append(c.RejectedVersions, rejected)
			c.RejectedVersions = SortVersions(c.RejectedVersions)
			c.Severity = ConflictSeverity(selected, c.RejectedVersions)
		}
		res.conflicts[key] = c
	}

	register := func(crate, version string, depth int, parentKey, source string, features []string, targetTriple string) string {
		ck := CrateKey(crate, version)
		prev := winners[crate]
		if prev == nil {
			winners[crate] = &winnerState{
				version: version, depth: depth, parentKey: parentKey,
				crateKey: ck, source: source, features: SortFeatures(features),
			}
			res.crates[ck] = ResolvedCrate{
				CrateKey: ck, Crate: crate, Version: version,
				Depth: depth, Source: source, ActiveFeatures: SortFeatures(features),
			}
			res.crateTargets[ck] = targetTriple
			return ck
		}

		if depth == prev.depth && parentKey == prev.parentKey && version == prev.version {
			merged := UnionFeatures(prev.features, features)
			if len(merged) != len(prev.features) {
				prev.features = merged
				node := res.crates[prev.crateKey]
				node.ActiveFeatures = merged
				res.crates[prev.crateKey] = node
			}
			return prev.crateKey
		}

		contender := &winnerState{
			version: version, depth: depth, parentKey: parentKey,
			crateKey: ck, source: source, features: SortFeatures(features),
		}
		keep := prev
		if depth > prev.depth {
			keep = contender
			addRejected(crate, version, prev.version)
		} else if depth < prev.depth {
			addRejected(crate, prev.version, version)
			return prev.crateKey
		} else if parentKey > prev.parentKey {
			keep = contender
			addRejected(crate, version, prev.version)
		} else {
			addRejected(crate, prev.version, version)
			return prev.crateKey
		}

		if keep.crateKey != prev.crateKey {
			delete(res.crates, prev.crateKey)
			delete(res.crateTargets, prev.crateKey)
			winners[crate] = keep
			res.crates[keep.crateKey] = ResolvedCrate{
				CrateKey: keep.crateKey, Crate: crate, Version: keep.version,
				Depth: keep.depth, Source: keep.source, ActiveFeatures: keep.features,
			}
			res.crateTargets[keep.crateKey] = targetTriple
		}
		return winners[crate].crateKey
	}

	var walk func(parentKey string, parentDepth int)
	walk = func(parentKey string, parentDepth int) {
		childDepth := parentDepth + 1
		for _, edge := range edgesByParent[parentKey] {
			if _, excl := exclusions[edge.Child]; excl {
				res.framesRejected++
				continue
			}
			if edge.Optional {
				if _, decl := declared[edge.Child]; !decl {
					res.framesRejected++
					continue
				}
			}
			if childDepth > cap {
				res.truncatedTail++
				continue
			}
			ver, fromPin := ResolveVersion(edge.Child, edge.Version, pins)
			feats := EdgeFeatures(edge, pins, wsFeatures)
			feats = ExpandFeatureAliases(feats, sc.FeatureAliases)
			fromWS := fromPin
			src := SourceLabel(edge.Child, declared, members, fromWS)
			ck := register(edge.Child, ver, childDepth, parentKey, src, feats, edge.TargetTriple)
			res.edgesTraversed++
			walk(ck, childDepth)
		}
	}

	for _, d := range declaredProcessingOrder(sc) {
		ver, fromPin := ResolveVersion(d.Crate, d.Version, pins)
		feats := SortFeatures(d.Features)
		feats = ExpandFeatureAliases(feats, sc.FeatureAliases)
		if d.DefaultFeatures {
			for _, e := range edges {
				if e.Parent == "root" && e.Child == d.Crate {
					feats = UnionFeatures(feats, e.DefaultCrateFeatures)
				}
			}
		}
		if ws, ok := wsFeatures[d.Crate]; ok {
			feats = UnionFeatures(feats, ws)
		}
		src := SourceLabel(d.Crate, declared, members, fromPin)
		ck := register(d.Crate, ver, 1, "root", src, feats, "any")
		walk(ck, 1)
	}

	if len(sc.Declared) == 0 {
		walk("root", 0)
	}

	return res
}
