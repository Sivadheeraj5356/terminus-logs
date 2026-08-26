#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/reloclogic/evaluate.go <<'GO'
package reloclogic

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strconv"
	"strings"
)

// EvaluateBatch evaluates one relocation batch against the canon policy.
func EvaluateBatch(bf BatchFile, pol Policy) BatchResult {
	findings := analyze(bf, bf.Mappings, pol, false)
	rep := runReplay(bf, pol, findings)
	mapOK := !hasKind(findings, "relocation_loop") &&
		!hasKind(findings, "stale_mapping") &&
		!hasKind(findings, "shadowed_mapping")
	rewOK := !hasKind(findings, "reference_omission") &&
		!hasKind(findings, "reference_misrewrite") &&
		!hasKind(findings, "namespace_drift") &&
		!hasKind(findings, "nested_omission") &&
		!hasKind(findings, "cascade_gap") &&
		!hasKind(findings, "orphan_nested_observation") &&
		!hasKind(findings, "dangling_observation")
	isoOK := !hasKind(findings, "symbol_collision") && !hasKind(findings, "isolation_breach")
	idOK := !hasKind(findings, "identity_loss") && !hasKind(findings, "metadata_inconsistency")
	rbOK := !hasKind(findings, "rollback_incomplete")
	ok := len(findings) == 0 && mapOK && rewOK && isoOK && idOK && rbOK
	if findings == nil {
		findings = []Finding{}
	}
	return BatchResult{
		BatchID:      bf.BatchID,
		RelocationOK: ok,
		Findings:     findings,
		MappingOK:    mapOK,
		RewriteOK:    rewOK,
		IsolationOK:  isoOK,
		IdentityOK:   idOK,
		RollbackOK:   rbOK,
		Replay:       rep,
	}
}

func analyze(bf BatchFile, maps []Mapping, pol Policy, skipDigest bool) []Finding {
	sorted := sortMappings(maps)
	var out []Finding

	if cyc := mappingCycle(sorted); cyc != nil {
		out = append(out, Finding{
			Kind: "relocation_loop", Subject: strings.Join(cyc, ">"),
			RuleID: "reloc.relocation_loop",
		})
	}

	names := collectNames(bf.Units, true)
	for _, m := range sorted {
		used := false
		for _, n := range names {
			if matchesPrefix(n, m.FromPrefix) {
				used = true
				break
			}
		}
		if !used {
			out = append(out, Finding{
				Kind: "stale_mapping", Subject: m.FromPrefix,
				RuleID: "reloc.stale_mapping",
			})
		}
	}

	if pol.DetectShadowedMappings {
		out = append(out, shadowedFindings(sorted, names)...)
	}

	type symInfo struct {
		original string
		expected string
		unit     Unit
		nested   bool
		parent   string
	}
	var syms []symInfo
	type refInfo struct {
		id, original, expected string
		nested                 bool
		parent                 string
	}
	var refs []refInfo
	type resInfo struct {
		path, original, expected string
		nested                   bool
		parent                   string
	}
	var resources []resInfo

	var walk func(units []Unit, nested bool, parent string)
	walk = func(units []Unit, nested bool, parent string) {
		for _, u := range units {
			for _, s := range u.Symbols {
				ef := relocate(s.FQN, sorted, false, pol.ChainRelocations)
				ep := relocate(s.PkgPath, sorted, true, pol.ChainRelocations)
				pkgSlash := strings.ReplaceAll(pkgOf(ef), ".", "/")
				if pkgSlash != ep {
					out = append(out, Finding{
						Kind: "namespace_drift", Subject: s.FQN,
						Expected: pkgSlash, Observed: ep,
						RuleID: "reloc.namespace_drift",
					})
				}
				syms = append(syms, symInfo{s.FQN, ef, u, nested, parent})
			}
			for _, r := range u.Refs {
				el := relocate(r.Literal, sorted, false, pol.ChainRelocations)
				refs = append(refs, refInfo{r.ID, r.Literal, el, nested, parent})
			}
			for _, res := range u.Resources {
				ec := relocate(res.ContentRef, sorted, false, pol.ChainRelocations)
				resources = append(resources, resInfo{res.Path, res.ContentRef, ec, nested, parent})
			}
			if pol.CascadeNested && len(u.Nested) > 0 {
				walk(u.Nested, true, u.Path)
			}
		}
	}
	walk(bf.Units, false, "")

	byExp := map[string][]string{}
	for _, s := range syms {
		if pol.CollisionTopLevelOnly && s.nested {
			continue
		}
		if s.nested && !pol.CascadeNested {
			continue
		}
		byExp[s.expected] = append(byExp[s.expected], s.original)
	}
	for exp, origs := range byExp {
		uniq := uniqueSorted(origs)
		if len(uniq) > 1 {
			out = append(out, Finding{
				Kind: "symbol_collision", Subject: exp,
				Expected: strings.Join(uniq, ","),
				RuleID:   "reloc.symbol_collision",
			})
		}
	}

	if pol.ForbidCrossRootMerge {
		pkgRoots := map[string]map[string]bool{}
		for _, s := range syms {
			if s.nested && !pol.CascadeNested {
				continue
			}
			pkg := pkgOf(s.expected)
			if pkgRoots[pkg] == nil {
				pkgRoots[pkg] = map[string]bool{}
			}
			pkgRoots[pkg][s.unit.Root] = true
		}
		for pkg, roots := range pkgRoots {
			if len(roots) > 1 {
				rs := make([]string, 0, len(roots))
				for r := range roots {
					rs = append(rs, r)
				}
				sort.Strings(rs)
				out = append(out, Finding{
					Kind: "isolation_breach", Subject: pkg,
					Expected: strings.Join(rs, ","),
					RuleID:   "reloc.isolation_breach",
				})
			}
		}
	}

	obsSym := map[string]ObservedSymbol{}
	for _, s := range bf.Observed.Symbols {
		obsSym[s.Original] = s
	}
	obsRef := map[string]ObservedRef{}
	for _, r := range bf.Observed.Refs {
		obsRef[r.ID] = r
	}
	obsRes := map[string]ObservedResource{}
	for _, r := range bf.Observed.Resources {
		obsRes[r.Path] = r
	}
	obsNestedSym := map[string]ObservedSymbol{}
	obsNestedRef := map[string]ObservedRef{}
	for _, n := range bf.Observed.Nested {
		for _, s := range n.Symbols {
			obsNestedSym[n.UnitPath+"#"+s.Original] = s
		}
		for _, r := range n.Refs {
			obsNestedRef[n.UnitPath+"#"+r.ID] = r
		}
	}

	gapParents := map[string]bool{}
	if pol.CascadeNested {
		for _, u := range bf.Units {
			if len(u.Nested) == 0 {
				continue
			}
			needs := false
			for _, nu := range u.Nested {
				for _, s := range nu.Symbols {
					if relocate(s.FQN, sorted, false, pol.ChainRelocations) != s.FQN {
						needs = true
					}
				}
				for _, r := range nu.Refs {
					if relocate(r.Literal, sorted, false, pol.ChainRelocations) != r.Literal {
						needs = true
					}
				}
			}
			if needs && !bf.Observed.NestedApplied {
				gapParents[u.Path] = true
				out = append(out, Finding{
					Kind: "cascade_gap", Subject: u.Path,
					Expected: "true", Observed: "false",
					RuleID: "reloc.cascade_gap",
				})
			}
		}
	}

	if pol.CascadeGapSuppressesNested {
		for parent := range gapParents {
			hasPayload := false
			for _, n := range bf.Observed.Nested {
				if n.UnitPath != parent {
					continue
				}
				if pol.OrphanRequiresPayload {
					if len(n.Symbols) > 0 || len(n.Refs) > 0 {
						hasPayload = true
					}
				} else {
					hasPayload = true
				}
			}
			if hasPayload {
				out = append(out, Finding{
					Kind: "orphan_nested_observation", Subject: parent,
					Expected: "", Observed: "present",
					RuleID: "reloc.orphan_nested_observation",
				})
			}
		}
	}

	for _, s := range syms {
		if s.nested && !pol.CascadeNested {
			continue
		}
		if pol.CascadeGapSuppressesNested && s.nested && gapParents[s.parent] {
			continue
		}
		var obsFQN string
		subject := s.original
		if s.nested {
			o, ok := obsNestedSym[s.parent+"#"+s.original]
			if ok {
				obsFQN = o.FQN
			} else {
				obsFQN = s.original
			}
			subject = s.parent + "#" + s.original
		} else {
			o, ok := obsSym[s.original]
			if ok {
				obsFQN = o.FQN
			} else {
				obsFQN = s.original
			}
		}
		if s.expected != s.original && obsFQN == s.original {
			kind := "reference_omission"
			if s.nested {
				kind = "nested_omission"
			}
			out = append(out, Finding{
				Kind: kind, Subject: subject,
				Expected: s.expected, Observed: obsFQN,
				RuleID: "reloc." + kind,
			})
		} else if obsFQN != s.original && obsFQN != s.expected {
			out = append(out, Finding{
				Kind: "reference_misrewrite", Subject: subject,
				Expected: s.expected, Observed: obsFQN,
				RuleID: "reloc.reference_misrewrite",
			})
		}
	}

	for _, r := range refs {
		if r.nested && !pol.CascadeNested {
			continue
		}
		if pol.CascadeGapSuppressesNested && r.nested && gapParents[r.parent] {
			continue
		}
		var obsLit string
		subject := r.id
		if r.nested {
			o, ok := obsNestedRef[r.parent+"#"+r.id]
			if ok {
				obsLit = o.Literal
			} else {
				obsLit = r.original
			}
			subject = r.parent + "#" + r.id
		} else {
			o, ok := obsRef[r.id]
			if ok {
				obsLit = o.Literal
			} else {
				obsLit = r.original
			}
		}
		if r.expected != r.original && obsLit == r.original {
			kind := "reference_omission"
			if r.nested {
				kind = "nested_omission"
			}
			out = append(out, Finding{
				Kind: kind, Subject: subject,
				Expected: r.expected, Observed: obsLit,
				RuleID: "reloc." + kind,
			})
		} else if obsLit != r.original && obsLit != r.expected {
			out = append(out, Finding{
				Kind: "reference_misrewrite", Subject: subject,
				Expected: r.expected, Observed: obsLit,
				RuleID: "reloc.reference_misrewrite",
			})
		}
	}

	if pol.CheckResourceRewrites {
		for _, res := range resources {
			if res.nested && !pol.CascadeNested {
				continue
			}
			if pol.CascadeGapSuppressesNested && res.nested && gapParents[res.parent] {
				continue
			}
			expPath := res.path
			if strings.Contains(res.path, "/") {
				expPath = relocate(res.path, sorted, true, pol.ChainRelocations)
			}
			o, ok := obsRes[res.path]
			if !ok {
				o, ok = obsRes[expPath]
			}
			obsCR := res.original
			if ok {
				obsCR = o.ContentRef
			}
			subject := "res:" + res.path
			if res.nested {
				subject = res.parent + "#res:" + res.path
			}
			if res.expected != res.original && obsCR == res.original {
				out = append(out, Finding{
					Kind: "reference_omission", Subject: subject,
					Expected: res.expected, Observed: obsCR,
					RuleID: "reloc.reference_omission",
				})
			} else if obsCR != res.original && obsCR != res.expected {
				out = append(out, Finding{
					Kind: "reference_misrewrite", Subject: subject,
					Expected: res.expected, Observed: obsCR,
					RuleID: "reloc.reference_misrewrite",
				})
			}
		}
	}

	if bf.PreserveIdentity {
		if bf.Observed.Identity.Group != bf.Identity.Group {
			out = append(out, Finding{
				Kind: "identity_loss", Subject: "group",
				Expected: bf.Identity.Group, Observed: bf.Observed.Identity.Group,
				RuleID: "reloc.identity_loss",
			})
		}
		if bf.Observed.Identity.Artifact != bf.Identity.Artifact {
			out = append(out, Finding{
				Kind: "identity_loss", Subject: "artifact",
				Expected: bf.Identity.Artifact, Observed: bf.Observed.Identity.Artifact,
				RuleID: "reloc.identity_loss",
			})
		}
		if pol.PreserveIdentityVersion && bf.Observed.Identity.Version != bf.Identity.Version {
			out = append(out, Finding{
				Kind: "identity_loss", Subject: "version",
				Expected: bf.Identity.Version, Observed: bf.Observed.Identity.Version,
				RuleID: "reloc.identity_loss",
			})
		}
	}

	epochBad := false
	if pol.RequireExactRelocatorEpoch {
		epochBad = bf.Observed.Metadata.RelocatorEpoch != pol.RequiredRelocatorEpoch
	} else {
		epochBad = bf.Observed.Metadata.RelocatorEpoch < pol.RequiredRelocatorEpoch
	}
	if epochBad {
		out = append(out, Finding{
			Kind: "metadata_inconsistency", Subject: "relocator_epoch",
			Expected: strconv.Itoa(pol.RequiredRelocatorEpoch),
			Observed: strconv.Itoa(bf.Observed.Metadata.RelocatorEpoch),
			RuleID:   "reloc.metadata_inconsistency",
		})
	}

	if pol.DetectDanglingObservations {
		knownSym := map[string]bool{}
		knownRef := map[string]bool{}
		var mark func([]Unit)
		mark = func(us []Unit) {
			for _, u := range us {
				for _, s := range u.Symbols {
					knownSym[s.FQN] = true
				}
				for _, r := range u.Refs {
					knownRef[r.ID] = true
				}
				if len(u.Nested) > 0 {
					mark(u.Nested)
				}
			}
		}
		mark(bf.Units)
		for _, s := range bf.Observed.Symbols {
			if !knownSym[s.Original] {
				out = append(out, Finding{
					Kind: "dangling_observation", Subject: s.Original,
					Expected: "", Observed: s.FQN,
					RuleID: "reloc.dangling_observation",
				})
			}
		}
		for _, r := range bf.Observed.Refs {
			if !knownRef[r.ID] {
				out = append(out, Finding{
					Kind: "dangling_observation", Subject: "ref:" + r.ID,
					Expected: "", Observed: r.Literal,
					RuleID: "reloc.dangling_observation",
				})
			}
		}
		if pol.DetectDanglingNested {
			for _, n := range bf.Observed.Nested {
				parentKnown := map[string]bool{}
				var markParent func([]Unit)
				markParent = func(us []Unit) {
					for _, u := range us {
						if u.Path == n.UnitPath {
							var walkNest func([]Unit)
							walkNest = func(ns []Unit) {
								for _, nu := range ns {
									for _, s := range nu.Symbols {
										parentKnown[s.FQN] = true
									}
									if len(nu.Nested) > 0 {
										walkNest(nu.Nested)
									}
								}
							}
							walkNest(u.Nested)
						}
						if len(u.Nested) > 0 {
							markParent(u.Nested)
						}
					}
				}
				markParent(bf.Units)
				for _, s := range n.Symbols {
					if !parentKnown[s.Original] {
						out = append(out, Finding{
							Kind: "dangling_observation", Subject: n.UnitPath + "#" + s.Original,
							Expected: "", Observed: s.FQN,
							RuleID: "reloc.dangling_observation",
						})
					}
				}
			}
		}
	}

	if !skipDigest {
		sim := simulateDigest(bf, pol)
		if bf.Observed.Digest != sim {
			out = append(out, Finding{
				Kind: "rollback_incomplete", Subject: "digest",
				Expected: sim, Observed: bf.Observed.Digest,
				RuleID: "reloc.rollback_incomplete",
			})
		}
	}

	return dedupeSort(out)
}

func shadowedFindings(maps []Mapping, names []string) []Finding {
	var out []Finding
	for _, m := range maps {
		shadowers := []string{}
		for _, n := range maps {
			if n.FromPrefix == m.FromPrefix {
				continue
			}
			if isStrictPackagePrefix(m.FromPrefix, n.FromPrefix) {
				shadowers = append(shadowers, n.FromPrefix)
			}
		}
		if len(shadowers) == 0 {
			continue
		}
		won := false
		for _, name := range names {
			sel := selectMapping(name, maps, false)
			if sel != nil && sel.FromPrefix == m.FromPrefix {
				won = true
				break
			}
		}
		if !won {
			sort.Strings(shadowers)
			out = append(out, Finding{
				Kind: "shadowed_mapping", Subject: m.FromPrefix,
				Expected: shadowers[0], Observed: "",
				RuleID: "reloc.shadowed_mapping",
			})
		}
	}
	return out
}

func isStrictPackagePrefix(shorter, longer string) bool {
	return longer != shorter && (strings.HasPrefix(longer, shorter+".") || strings.HasPrefix(longer, shorter+"/"))
}

func selectMapping(s string, maps []Mapping, slash bool) *Mapping {
	bestLen := -1
	var best *Mapping
	for i := range maps {
		m := &maps[i]
		fp := m.FromPrefix
		if slash {
			fp = strings.ReplaceAll(fp, ".", "/")
		}
		if !matchesPrefix(s, fp) {
			continue
		}
		if len(fp) > bestLen {
			bestLen = len(fp)
			best = m
		}
	}
	return best
}

func runReplay(bf BatchFile, pol Policy, full []Finding) Replay {
	if bf.Replay == nil || len(bf.Replay.Schedules) == 0 {
		return Replay{SchedulesRun: 0, SchedulesPassed: 0, Stable: true}
	}
	schedules := bf.Replay.Schedules
	run := len(schedules)
	passed := 0
	fullCount := len(bf.Mappings)
	allPrefix := true
	allFull := true
	knownSeq := map[int]bool{}
	for _, m := range bf.Mappings {
		knownSeq[m.Seq] = true
	}
	for _, sch := range schedules {
		order := make([]int, 0, len(sch.MappingSeqOrder))
		for _, seq := range sch.MappingSeqOrder {
			if pol.ReplayIgnoreUnknownSeqs && !knownSeq[seq] {
				continue
			}
			order = append(order, seq)
		}
		if len(order) < fullCount {
			allFull = false
		} else {
			allPrefix = false
		}
		allowed := map[int]bool{}
		for _, seq := range order {
			allowed[seq] = true
		}
		subset := make([]Mapping, 0)
		for _, m := range bf.Mappings {
			if allowed[m.Seq] {
				subset = append(subset, m)
			}
		}
		sub := analyze(bf, subset, pol, pol.ReplaySkipsDigest)
		if len(sub) == 0 {
			passed++
		}
	}
	stable := passed == run
	if len(full) > 0 {
		if pol.PrefixStableOnFindings && allPrefix {
			stable = true
		}
		if pol.FullUnstableOnFindings && allFull {
			stable = false
		}
	}
	return Replay{SchedulesRun: run, SchedulesPassed: passed, Stable: stable}
}

func sortMappings(maps []Mapping) []Mapping {
	out := append([]Mapping(nil), maps...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Priority != out[j].Priority {
			return out[i].Priority < out[j].Priority
		}
		return out[i].FromPrefix < out[j].FromPrefix
	})
	return out
}

func matchesPrefix(s, pref string) bool {
	return s == pref || strings.HasPrefix(s, pref+".") || strings.HasPrefix(s, pref+"/")
}

func relocate(s string, maps []Mapping, slash bool, chain bool) string {
	cur := s
	seen := map[string]bool{cur: true}
	for {
		nxt := relocateOnce(cur, maps, slash)
		if nxt == cur {
			return cur
		}
		if !chain {
			return nxt
		}
		if seen[nxt] {
			return nxt
		}
		seen[nxt] = true
		cur = nxt
	}
}

func relocateOnce(s string, maps []Mapping, slash bool) string {
	best := selectMapping(s, maps, slash)
	if best == nil {
		return s
	}
	fp := best.FromPrefix
	tp := best.ToPrefix
	if slash {
		fp = strings.ReplaceAll(fp, ".", "/")
		tp = strings.ReplaceAll(tp, ".", "/")
	}
	return tp + s[len(fp):]
}

func pkgOf(fqn string) string {
	i := strings.LastIndex(fqn, ".")
	if i < 0 {
		return ""
	}
	return fqn[:i]
}

func mappingCycle(maps []Mapping) []string {
	graph := map[string]string{}
	for _, m := range maps {
		graph[m.FromPrefix] = m.ToPrefix
	}
	nodes := map[string]bool{}
	for a, b := range graph {
		nodes[a] = true
		nodes[b] = true
	}
	keys := make([]string, 0, len(nodes))
	for n := range nodes {
		keys = append(keys, n)
	}
	sort.Strings(keys)
	for _, start := range keys {
		seen := []string{}
		cur := start
		for {
			next, ok := graph[cur]
			if !ok {
				break
			}
			for i, s := range seen {
				if s == cur {
					body := append([]string{}, seen[i:]...)
					minI := 0
					for j := 1; j < len(body); j++ {
						if body[j] < body[minI] {
							minI = j
						}
					}
					rot := append([]string{}, body[minI:]...)
					rot = append(rot, body[:minI]...)
					rot = append(rot, rot[0])
					return rot
				}
			}
			seen = append(seen, cur)
			cur = next
			if len(seen) > len(nodes)+2 {
				break
			}
		}
	}
	return nil
}

func collectNames(units []Unit, includeNested bool) []string {
	var out []string
	var walk func([]Unit)
	walk = func(us []Unit) {
		for _, u := range us {
			for _, s := range u.Symbols {
				out = append(out, s.FQN)
			}
			for _, r := range u.Refs {
				out = append(out, r.Literal)
			}
			for _, res := range u.Resources {
				out = append(out, res.ContentRef)
			}
			if includeNested && len(u.Nested) > 0 {
				walk(u.Nested)
			}
		}
	}
	walk(units)
	return out
}


func effectiveMapBind(bf BatchFile, pol Policy) string {
	maps := sortMappings(bf.Mappings)
	names := collectNames(bf.Units, true)
	stale := map[string]bool{}
	for _, m := range maps {
		used := false
		for _, n := range names {
			if matchesPrefix(n, m.FromPrefix) {
				used = true
				break
			}
		}
		if !used {
			stale[m.FromPrefix] = true
		}
	}
	shadowed := map[string]bool{}
	if pol.DetectShadowedMappings {
		for _, f := range shadowedFindings(maps, names) {
			shadowed[f.Subject] = true
		}
	}
	ordered := append([]Mapping(nil), bf.Mappings...)
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].Seq < ordered[j].Seq })
	prefs := make([]string, 0, len(ordered))
	cycleNodes := map[string]bool{}
	if pol.DigestExcludeCycleMaps {
		if cyc := mappingCycle(maps); cyc != nil {
			for _, n := range cyc {
				cycleNodes[n] = true
			}
		}
	}
	for _, m := range ordered {
		if pol.DigestBindEffectiveMaps && (stale[m.FromPrefix] || shadowed[m.FromPrefix]) {
			continue
		}
		if pol.DigestExcludeCycleMaps && cycleNodes[m.FromPrefix] {
			continue
		}
		prefs = append(prefs, m.FromPrefix)
	}
	if !pol.DigestMapBindOrderSeq {
		sort.Strings(prefs)
	}
	return strings.Join(prefs, ",")
}

func simulateDigest(bf BatchFile, pol Policy) string {
	syms := []string{}
	resRefs := []string{}
	var walk func([]Unit)
	walk = func(us []Unit) {
		for _, u := range us {
			for _, s := range u.Symbols {
				syms = append(syms, s.FQN)
			}
			for _, r := range u.Resources {
				resRefs = append(resRefs, r.ContentRef)
			}
			if len(u.Nested) > 0 {
				walk(u.Nested)
			}
		}
	}
	walk(bf.Units)
	sort.Strings(syms)
	sort.Strings(resRefs)
	var digest string
	if pol.DigestBindResources {
		digest = shaHex(bf.BatchID + "|" + strings.Join(syms, ",") + "|res|" + strings.Join(resRefs, ","))
	} else {
		digest = shaHex(bf.BatchID + "|" + strings.Join(syms, ","))
	}
	mapBind := ""
	if pol.DigestBindActiveMaps {
		mapBind = effectiveMapBind(bf, pol)
	}
	steps := append([]Step(nil), bf.Steps...)
	sort.Slice(steps, func(i, j int) bool { return steps[i].Seq < steps[j].Seq })
	for _, st := range steps {
		if st.Op != "apply" {
			continue
		}
		if !st.Fail {
			if pol.DigestBindActiveMaps {
				digest = shaHex(digest + "|ok|" + strconv.Itoa(st.Seq) + "|maps|" + mapBind)
			} else {
				digest = shaHex(digest + "|ok|" + strconv.Itoa(st.Seq))
			}
		} else if st.Rollback {
			// unchanged
		} else {
			digest = shaHex(digest + "|fail|" + strconv.Itoa(st.Seq))
		}
	}
	return digest
}

func shaHex(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

func hasKind(v []Finding, kind string) bool {
	for _, x := range v {
		if x.Kind == kind {
			return true
		}
	}
	return false
}

func uniqueSorted(v []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(v))
	for _, x := range v {
		if seen[x] {
			continue
		}
		seen[x] = true
		out = append(out, x)
	}
	sort.Strings(out)
	return out
}

func dedupeSort(v []Finding) []Finding {
	seen := map[string]bool{}
	out := make([]Finding, 0, len(v))
	for _, x := range v {
		key := x.Kind + "|" + x.Subject + "|" + x.Expected + "|" + x.Observed + "|" + x.RuleID
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, x)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Kind != out[j].Kind {
			return out[i].Kind < out[j].Kind
		}
		if out[i].Subject != out[j].Subject {
			return out[i].Subject < out[j].Subject
		}
		if out[i].Expected != out[j].Expected {
			return out[i].Expected < out[j].Expected
		}
		return out[i].Observed < out[j].Observed
	})
	return out
}

GO

make build

test -x /app/bin/reloccheck
test "$(wc -c < /app/bin/reloccheck | tr -d ' ')" -gt 2048

mkdir -p /app/artifacts
rm -f /app/artifacts/relocation_consistency_report.json
/app/bin/reloccheck
test -s /app/artifacts/relocation_consistency_report.json
