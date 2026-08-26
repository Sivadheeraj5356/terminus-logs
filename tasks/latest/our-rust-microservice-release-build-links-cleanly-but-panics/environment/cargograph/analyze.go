package cargograph

import "sort"

func Analyze(sc Scenario) ScenarioOut {
	filtered, dupSkipped := FilterEdges(sc.Edges)
	pins := ApplyWorkspacePins(sc)
	declared := DeclaredMap(sc)
	members := WorkspaceMemberSet(sc)
	exclusions := exclusionSet(sc)

	res := resolveGraph(sc, filtered, pins, sc.WorkspaceFeatures, declared, members, exclusions, true)
	AssignResolutionReasons(res.conflicts, pins)

	resolved := make([]ResolvedCrate, 0, len(res.crates))
	for _, c := range res.crates {
		resolved = append(resolved, c)
	}
	sort.Slice(resolved, func(i, j int) bool {
		return resolved[i].CrateKey < resolved[j].CrateKey
	})

	runtimeSet := make([]string, 0)
	for _, c := range resolved {
		target := res.crateTargets[c.CrateKey]
		if !CrateOnRuntimeSet(c, target, sc.ProfileMode) {
			continue
		}
		tags := sc.FeatureTags[c.Crate]
		filteredFeats := FilterRuntimeFeatures(c.ActiveFeatures, sc.BuildProfile, tags)
		if len(filteredFeats) == 0 && sc.BuildProfile == "release" {
			hasNonDev := false
			dev := make(map[string]struct{})
			for _, f := range tags.DevOnlyFeatures {
				dev[f] = struct{}{}
			}
			for _, f := range c.ActiveFeatures {
				if _, ok := dev[f]; !ok {
					hasNonDev = true
					break
				}
			}
			if !hasNonDev && len(c.ActiveFeatures) > 0 {
				continue
			}
		}
		if len(filteredFeats) > 0 || sc.BuildProfile != "release" {
			runtimeSet = append(runtimeSet, c.CrateKey)
		}
	}
	sort.Strings(runtimeSet)

	conflicts := make([]FeatureConflict, 0, len(res.conflicts))
	for _, c := range res.conflicts {
		conflicts = append(conflicts, c)
	}
	sort.Slice(conflicts, func(i, j int) bool {
		if conflicts[i].Crate != conflicts[j].Crate {
			return conflicts[i].Crate < conflicts[j].Crate
		}
		return conflicts[i].SelectedVersion < conflicts[j].SelectedVersion
	})

	status := "CLEAN"
	if len(conflicts) > 0 {
		status = "CONFLICT"
	}

	payloadDigest, _ := ScenarioPayloadDigest(sc.ScenarioID)
	payloadCRC32, _ := ScenarioPayloadCRC32(sc.ScenarioID)
	payloadLen, _ := ScenarioPayloadLen(sc.ScenarioID)

	return ScenarioOut{
		ScenarioID:             sc.ScenarioID,
		Status:                 status,
		DuplicateEdgesSkipped:  dupSkipped,
		FramesRejected:         res.framesRejected,
		TruncatedTail:          res.truncatedTail,
		EdgesTraversed:         res.edgesTraversed,
		ConflictRejectionCount: ConflictRejectionCount(conflicts),
		ConflictRowsPurged:     res.conflictRowsPurged,
		ScenarioPayloadDigest:  payloadDigest,
		ScenarioPayloadCRC32:   payloadCRC32,
		ScenarioPayloadLen:     payloadLen,
		ScenarioPayloadPlus:    ScenarioPayloadPlus(payloadLen, dupSkipped, res.framesRejected, res.truncatedTail),
		PartialFeatureLiterals: CountPartialFeatureLiterals(resolved),
		WireReserved:           0,
		ResolvedCrates:         resolved,
		RuntimeFeatureSet:      runtimeSet,
		FeatureConflicts:       conflicts,
	}
}
