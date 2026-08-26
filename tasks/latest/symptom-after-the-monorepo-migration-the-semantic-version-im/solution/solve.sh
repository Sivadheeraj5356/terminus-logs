#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/propagation/semver/compare.go <<'COMPARE_EOF'
package semver

import (
	"strconv"
	"strings"
)

type Version struct {
	Major      int
	Minor      int
	Patch      int
	Prerelease string
}

func Parse(raw string) (Version, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return Version{}, false
	}
	parts := strings.SplitN(raw, "+", 2)
	core := parts[0]
	pre := ""
	if idx := strings.Index(core, "-"); idx >= 0 {
		pre = core[idx+1:]
		core = core[:idx]
	}
	seg := strings.Split(core, ".")
	if len(seg) != 3 {
		return Version{}, false
	}
	maj, e1 := strconv.Atoi(seg[0])
	min, e2 := strconv.Atoi(seg[1])
	pat, e3 := strconv.Atoi(seg[2])
	if e1 != nil || e2 != nil || e3 != nil {
		return Version{}, false
	}
	return Version{Major: maj, Minor: min, Patch: pat, Prerelease: pre}, true
}

func prereleaseCmp(a, b string) int {
	if a == b {
		return 0
	}
	if a == "" {
		return 1
	}
	if b == "" {
		return -1
	}
	ap := strings.Split(a, ".")
	bp := strings.Split(b, ".")
	n := len(ap)
	if len(bp) > n {
		n = len(bp)
	}
	for i := 0; i < n; i++ {
		av := ""
		bv := ""
		if i < len(ap) {
			av = ap[i]
		}
		if i < len(bp) {
			bv = bp[i]
		}
		if av == bv {
			continue
		}
		ai, ae := strconv.Atoi(av)
		bi, be := strconv.Atoi(bv)
		if ae == nil && be == nil {
			if ai != bi {
				if ai < bi {
					return -1
				}
				return 1
			}
			continue
		}
		if av < bv {
			return -1
		}
		return 1
	}
	return 0
}

func Compare(a, b Version) int {
	if a.Major != b.Major {
		if a.Major < b.Major {
			return -1
		}
		return 1
	}
	if a.Minor != b.Minor {
		if a.Minor < b.Minor {
			return -1
		}
		return 1
	}
	if a.Patch != b.Patch {
		if a.Patch < b.Patch {
			return -1
		}
		return 1
	}
	return prereleaseCmp(a.Prerelease, b.Prerelease)
}

func BumpType(oldV, newV string) string {
	old, ok1 := Parse(oldV)
	new, ok2 := Parse(newV)
	if !ok1 || !ok2 || Compare(new, old) <= 0 {
		return "none"
	}
	if new.Major > old.Major {
		return "major"
	}
	if new.Minor > old.Minor {
		return "minor"
	}
	return "patch"
}

func Satisfies(constraint, version string) bool {
	constraint = strings.TrimSpace(constraint)
	version = strings.TrimSpace(version)
	ver, ok := Parse(version)
	if !ok {
		return false
	}
	if strings.Contains(constraint, " - ") {
		bits := strings.SplitN(constraint, " - ", 2)
		if len(bits) != 2 {
			return false
		}
		lo, lok := Parse(strings.TrimSpace(bits[0]))
		hi, hok := Parse(strings.TrimSpace(bits[1]))
		if !lok || !hok {
			return false
		}
		return Compare(ver, lo) >= 0 && Compare(ver, hi) <= 0
	}
	if strings.HasPrefix(constraint, ">=") {
		base, ok := Parse(strings.TrimSpace(constraint[2:]))
		return ok && Compare(ver, base) >= 0
	}
	if strings.HasPrefix(constraint, "^") {
		base, ok := Parse(strings.TrimSpace(constraint[1:]))
		if !ok {
			return false
		}
		if base.Major > 0 {
			return Compare(ver, base) >= 0 && ver.Major == base.Major
		}
		return Compare(ver, base) >= 0 && ver.Major == 0 && ver.Minor == base.Minor
	}
	if strings.HasPrefix(constraint, "~") {
		base, ok := Parse(strings.TrimSpace(constraint[1:]))
		if !ok {
			return false
		}
		return Compare(ver, base) >= 0 && ver.Major == base.Major && ver.Minor == base.Minor
	}
	base, ok := Parse(constraint)
	if !ok {
		return false
	}
	return Compare(ver, base) == 0
}
COMPARE_EOF

cat > /app/propagation/simulate/propagate.go <<'PROP_EOF'
package simulate

import (
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"svis/contracts"
	"svis/propagation/semver"
)

var weightKeys = []string{
	"constraint_break", "blast_radius", "schedule_slip", "peer_mismatch", "bump_severity",
}

func projectNum(pid string) int {
	parts := strings.Split(pid, "_")
	if len(parts) != 2 {
		return 1
	}
	n, err := strconv.Atoi(parts[1])
	if err != nil || n <= 0 {
		return 1
	}
	return n
}

func round4(v float64) float64 {
	return math.Round(v*10000) / 10000
}

func defaults(n int) (float64, int, map[string]float64) {
	return 0.55 + float64(n%5)*0.03, 3 + (n % 4), map[string]float64{
		"constraint_break": 0.30, "blast_radius": 0.25, "schedule_slip": 0.15,
		"peer_mismatch": 0.15, "bump_severity": 0.15,
	}
}

func mergeWeights(base, override map[string]float64) map[string]float64 {
	out := make(map[string]float64)
	for k, v := range base {
		out[k] = v
	}
	for k, v := range override {
		out[k] = v
	}
	return out
}

func tierFor(score float64) string {
	switch {
	case score >= 0.75:
		return "CRITICAL"
	case score >= 0.50:
		return "HIGH"
	case score >= 0.25:
		return "MEDIUM"
	default:
		return "LOW"
	}
}

func nodeVersion(graph contracts.ReleaseGraph, name string) string {
	for _, n := range graph.Nodes {
		if n.Name == name {
			return n.Version
		}
	}
	return ""
}

func upgradeOrder(graph contracts.ReleaseGraph, proposed []string) []string {
	edges := make([]contracts.GraphEdge, 0)
	for _, e := range graph.Edges {
		if e.EdgeType != "peer" {
			edges = append(edges, e)
		}
	}
	remaining := make(map[string]struct{})
	for _, p := range proposed {
		remaining[p] = struct{}{}
	}
	order := make([]string, 0, len(proposed))
	for len(remaining) > 0 {
		ready := make([]string, 0)
		for pkg := range remaining {
			blocked := false
			for _, e := range edges {
				if e.Consumer == pkg {
					if _, ok := remaining[e.Provider]; ok {
						blocked = true
						break
					}
				}
			}
			if !blocked {
				ready = append(ready, pkg)
			}
		}
		sort.Strings(ready)
		if len(ready) == 0 {
			rest := make([]string, 0, len(remaining))
			for p := range remaining {
				rest = append(rest, p)
			}
			sort.Strings(rest)
			order = append(order, rest...)
			break
		}
		pick := ready[0]
		order = append(order, pick)
		delete(remaining, pick)
	}
	return order
}

func blastRadius(graph contracts.ReleaseGraph, provider string) int {
	queue := make([]string, 0)
	seen := make(map[string]struct{})
	for _, e := range graph.Edges {
		if e.EdgeType == "peer" {
			continue
		}
		if e.Provider == provider {
			queue = append(queue, e.Consumer)
		}
	}
	affected := make(map[string]struct{})
	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]
		if _, ok := seen[cur]; ok {
			continue
		}
		seen[cur] = struct{}{}
		affected[cur] = struct{}{}
		for _, e := range graph.Edges {
			if e.EdgeType == "peer" {
				continue
			}
			if e.Provider == cur {
				queue = append(queue, e.Consumer)
			}
		}
	}
	return len(affected)
}

func Simulate(cfg contracts.ProjectConfig) contracts.ProjectReport {
	n := projectNum(cfg.ProjectID)
	riskDef, blastDef, baseW := defaults(n)
	weights := mergeWeights(baseW, cfg.Weights)
	riskCutoff := riskDef
	if cfg.RiskCutoff != nil {
		riskCutoff = *cfg.RiskCutoff
	}
	blastThreshold := blastDef
	if cfg.BlastThreshold != nil {
		blastThreshold = *cfg.BlastThreshold
	}
	graph := cfg.Graph
	versions := make(map[string]string)
	for _, node := range graph.Nodes {
		versions[node.Name] = node.Version
	}
	proposedMap := make(map[string]contracts.ProposedBump)
	for _, p := range graph.Proposed {
		proposedMap[p.Package] = p
		versions[p.Package] = p.Target
	}

	violations := make([]string, 0)
	peerViolations := 0
	peerEdges := 0
	requiredEdges := 0
	for _, edge := range graph.Edges {
		if edge.EdgeType == "peer" {
			peerEdges++
			if p, ok := proposedMap[edge.Provider]; ok {
				if !semver.Satisfies(edge.Constraint, p.Target) {
					peerViolations++
				}
			}
			continue
		}
		if edge.Required {
			requiredEdges++
		}
		resolved := versions[edge.Provider]
		if !semver.Satisfies(edge.Constraint, resolved) && edge.Required {
			violations = append(violations, fmt.Sprintf("%s|%s|%s|%s", edge.Consumer, edge.Provider, edge.Constraint, resolved))
		}
	}
	sort.Strings(violations)

	scheduleConflicts := make([]string, 0)
	for _, p := range graph.Proposed {
		if p.ReleaseDate > cfg.FreezeDate {
			scheduleConflicts = append(scheduleConflicts, fmt.Sprintf("%s|%s|%s", p.Package, p.ReleaseDate, cfg.FreezeDate))
		}
	}
	sort.Strings(scheduleConflicts)

	bumpTypes := make(map[string]string)
	severityVals := make([]float64, 0)
	blast := make(map[string]int)
	maxBlast := 0
	for _, p := range graph.Proposed {
		old := nodeVersion(graph, p.Package)
		bt := semver.BumpType(old, p.Target)
		bumpTypes[p.Package] = bt
		sev := map[string]float64{"major": 1.0, "minor": 0.5, "patch": 0.1, "none": 0.0}[bt]
		severityVals = append(severityVals, sev)
		br := blastRadius(graph, p.Package)
		blast[p.Package] = br
		if br > maxBlast {
			maxBlast = br
		}
	}

	cb := math.Min(1.0, float64(len(violations))/math.Max(1, float64(requiredEdges)))
	bb := math.Min(1.0, float64(maxBlast)/math.Max(1, float64(blastThreshold)))
	sc := math.Min(1.0, float64(len(scheduleConflicts))/math.Max(1, float64(len(graph.Proposed))))
	pc := 0.0
	if peerEdges > 0 {
		pc = math.Min(1.0, float64(peerViolations)/float64(peerEdges))
	}
	bs := 0.0
	if len(severityVals) > 0 {
		sum := 0.0
		for _, v := range severityVals {
			sum += v
		}
		bs = sum / float64(len(severityVals))
	}
	wsum := 0.0
	compSum := 0.0
	compSum += cb * weights["constraint_break"]
	compSum += bb * weights["blast_radius"]
	compSum += sc * weights["schedule_slip"]
	compSum += pc * weights["peer_mismatch"]
	compSum += bs * weights["bump_severity"]
	for _, k := range weightKeys {
		wsum += weights[k]
	}
	risk := round4(compSum / wsum)

	status := "SAFE"
	if len(violations) > 0 {
		status = "BLOCKED"
	} else if risk >= riskCutoff || len(scheduleConflicts) > 0 {
		status = "RISK"
	}

	paths := make([]string, 0)
	for _, v := range violations {
		parts := strings.SplitN(v, "|", 4)
		cons, prov, _, resolved := parts[0], parts[1], parts[2], parts[3]
		old := nodeVersion(graph, prov)
		bt := bumpTypes[prov]
		if bt == "" {
			bt = semver.BumpType(old, resolved)
		}
		paths = append(paths, fmt.Sprintf("%s->%s|%s|blocked", cons, prov, bt))
	}
	sort.Strings(paths)

	impacted := make([]contracts.PackageImpact, 0, len(graph.Proposed))
	for _, p := range graph.Proposed {
		br := blast[p.Package]
		pkgRisk := risk
		if maxBlast > 0 {
			pkgRisk = round4(risk * (float64(br) / float64(maxBlast)))
		}
		impacted = append(impacted, contracts.PackageImpact{
			PackageName: p.Package,
			BumpType:    bumpTypes[p.Package],
			BlastRadius: br,
			RiskScore:   pkgRisk,
			Tier:        tierFor(pkgRisk),
		})
	}
	sort.Slice(impacted, func(i, j int) bool {
		if impacted[i].BlastRadius != impacted[j].BlastRadius {
			return impacted[i].BlastRadius > impacted[j].BlastRadius
		}
		return impacted[i].PackageName < impacted[j].PackageName
	})

	proposedNames := make([]string, 0, len(graph.Proposed))
	for _, p := range graph.Proposed {
		proposedNames = append(proposedNames, p.Package)
	}

	return contracts.ProjectReport{
		ProjectID:            cfg.ProjectID,
		Status:               status,
		RiskScore:            risk,
		UpgradeOrder:         upgradeOrder(graph, proposedNames),
		PackagesImpacted:     impacted,
		ConstraintViolations: violations,
		PropagationPaths:     paths,
		ScheduleConflicts:    scheduleConflicts,
	}
}
PROP_EOF

cat > /app/impact-engine/main.go <<'MAIN_EOF'
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"svis/contracts"
	"svis/propagation/simulate"
)

func fmtFloat(v float64) string {
	s := strconv.FormatFloat(v, 'g', -1, 64)
	if !strings.ContainsAny(s, ".eE") {
		s += ".0"
	}
	return s
}

func writeJSONString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"', '\\':
			b.WriteByte('\\')
			b.WriteRune(r)
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
}

func writePackageImpact(b *strings.Builder, p contracts.PackageImpact) {
	b.WriteString("{\"package_name\":")
	writeJSONString(b, p.PackageName)
	b.WriteString(",\"bump_type\":")
	writeJSONString(b, p.BumpType)
	b.WriteString(",\"blast_radius\":")
	b.WriteString(strconv.Itoa(p.BlastRadius))
	b.WriteString(",\"risk_score\":")
	b.WriteString(fmtFloat(p.RiskScore))
	b.WriteString(",\"tier\":")
	writeJSONString(b, p.Tier)
	b.WriteByte('}')
}

func writeReport(path string, report contracts.ImpactReport) error {
	var b strings.Builder
	b.WriteString("{\"projects\":[")
	for pi, proj := range report.Projects {
		if pi > 0 {
			b.WriteByte(',')
		}
		b.WriteString("{\"project_id\":")
		writeJSONString(&b, proj.ProjectID)
		b.WriteString(",\"status\":")
		writeJSONString(&b, proj.Status)
		b.WriteString(",\"risk_score\":")
		b.WriteString(fmtFloat(proj.RiskScore))
		b.WriteString(",\"upgrade_order\":[")
		for ui, u := range proj.UpgradeOrder {
			if ui > 0 {
				b.WriteByte(',')
			}
			writeJSONString(&b, u)
		}
		b.WriteString("],\"packages_impacted\":[")
		for ii, pkg := range proj.PackagesImpacted {
			if ii > 0 {
				b.WriteByte(',')
			}
			writePackageImpact(&b, pkg)
		}
		b.WriteString("],\"constraint_violations\":[")
		for vi, v := range proj.ConstraintViolations {
			if vi > 0 {
				b.WriteByte(',')
			}
			writeJSONString(&b, v)
		}
		b.WriteString("],\"propagation_paths\":[")
		for pi2, p := range proj.PropagationPaths {
			if pi2 > 0 {
				b.WriteByte(',')
			}
			writeJSONString(&b, p)
		}
		b.WriteString("],\"schedule_conflicts\":[")
		for si, s := range proj.ScheduleConflicts {
			if si > 0 {
				b.WriteByte(',')
			}
			writeJSONString(&b, s)
		}
		b.WriteString("]}")
	}
	b.WriteString("]}\n")
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func main() {
	bundleDir := "/app/release-graphs"
	manifestPath := bundleDir + "/workspace_manifest.json"
	outPath := "/app/build/impact_report.json"

	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read manifest: %v\n", err)
		os.Exit(1)
	}
	var manifest contracts.WorkspaceManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		fmt.Fprintf(os.Stderr, "parse manifest: %v\n", err)
		os.Exit(1)
	}

	report := contracts.ImpactReport{Projects: make([]contracts.ProjectReport, 0, len(manifest.Projects))}
	for _, pid := range manifest.Projects {
		cfgPath := bundleDir + "/" + pid + ".json"
		cfgBytes, err := os.ReadFile(cfgPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		var cfg contracts.ProjectConfig
		if err := json.Unmarshal(cfgBytes, &cfg); err != nil {
			fmt.Fprintf(os.Stderr, "parse %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		if cfg.ProjectID == "" {
			cfg.ProjectID = pid
		}
		report.Projects = append(report.Projects, simulate.Simulate(cfg))
	}

	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := writeReport(outPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
MAIN_EOF

make clean || true
make build
make run
