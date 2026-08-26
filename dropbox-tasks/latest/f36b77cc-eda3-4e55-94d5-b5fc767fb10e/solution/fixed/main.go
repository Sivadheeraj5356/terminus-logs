package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const usage = "usage: bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>"

type requestFile struct {
	RequestID        string        `json:"request_id"`
	TargetPlatforms  []string      `json:"target_platforms"`
	RootFormulae     []rootRequest `json:"root_formulae"`
	AllowPrerelease  bool          `json:"allow_prerelease"`
	MaxNewDigests    int           `json:"max_new_digests"`
	MaxNewBytes      int           `json:"max_new_bytes"`
	RelocationPolicy string        `json:"relocation_policy"`
}

type rootRequest struct {
	Name            string   `json:"name"`
	VersionRange    string   `json:"version_range"`
	RequiredFeature []string `json:"required_features"`
	AllowKegOnly    bool     `json:"allow_keg_only"`
}

type formulaCatalog struct {
	Formulas []formulaRecord `json:"formulas"`
}

type formulaRecord struct {
	Name     string          `json:"name"`
	Versions []formulaChoice `json:"versions"`
}

type formulaChoice struct {
	Name         string
	Version      string           `json:"version"`
	Revision     int              `json:"revision"`
	Prerelease   bool             `json:"prerelease"`
	KegOnly      bool             `json:"keg_only"`
	Dependencies []dependencyEdge `json:"dependencies"`
	Bottles      []bottleChoice   `json:"bottles"`
}

type dependencyEdge struct {
	Name             string   `json:"name"`
	VersionRange     string   `json:"version_range"`
	RequiresFeatures []string `json:"requires_features"`
}

type bottleChoice struct {
	Platform     string `json:"platform"`
	Digest       string `json:"digest"`
	Bytes        int    `json:"bytes"`
	Cellar       string `json:"cellar"`
	Rebuild      int    `json:"rebuild"`
	Relocatable  bool   `json:"relocatable"`
	Codesigned   bool   `json:"codesigned"`
	RuntimeFloor string `json:"runtime_floor"`
}

type platformPolicyFile struct {
	Platforms []platformPolicy `json:"platforms"`
}

type platformPolicy struct {
	Platform          string `json:"platform"`
	RuntimeKind       string `json:"runtime_kind"`
	MinimumRuntime    string `json:"minimum_runtime"`
	RequireCodesigned bool   `json:"require_codesigned"`
}

type mirrorInventory struct {
	MirroredDigests []string `json:"mirrored_digests"`
}

type instance struct {
	Ref          string
	ParentRef    string
	Name         string
	VersionRange string
	Required     []string
	Root         bool
	AllowKegOnly bool
}

type searchState struct {
	Selected  map[string]formulaChoice
	Instances []instance
}

type solution struct {
	Selected  map[string]formulaChoice
	Instances []instance
}

type planner struct {
	Request       requestFile
	Policies      map[string]platformPolicy
	Mirrors       map[string]bool
	Formulae      map[string][]formulaChoice
	RootRequested map[string]rootRequest
	Best          *solution
}

type rootSelection struct {
	Name            string `json:"name"`
	SelectedVersion string `json:"selected_version"`
}

type bottleOutput struct {
	Platform     string `json:"platform"`
	Digest       string `json:"digest"`
	Cached       bool   `json:"cached"`
	Bytes        int    `json:"bytes"`
	Rebuild      int    `json:"rebuild"`
	Relocatable  bool   `json:"relocatable"`
	Codesigned   bool   `json:"codesigned"`
	RuntimeFloor string `json:"runtime_floor"`
}

type selectedFormula struct {
	Name          string             `json:"name"`
	Version       string             `json:"version"`
	Revision      int                `json:"revision"`
	ActiveFeature []string           `json:"active_features"`
	RootRequested bool               `json:"root_requested"`
	Dependencies  []dependencyOutput `json:"dependencies"`
	Bottles       []bottleOutput     `json:"bottles"`
}

type dependencyOutput struct {
	Name             string   `json:"name"`
	VersionRange     string   `json:"version_range"`
	RequiresFeatures []string `json:"requires_features"`
}

type promotionPlan struct {
	RequestID            string            `json:"request_id"`
	RelocationPolicy     string            `json:"relocation_policy"`
	TargetPlatforms      []string          `json:"target_platforms"`
	RootSelections       []rootSelection   `json:"root_selections"`
	SelectedFormulae     []selectedFormula `json:"selected_formulae"`
	UniqueNewDigestCount int               `json:"unique_new_digest_count"`
	TotalNewBytes        int               `json:"total_new_bytes"`
	TotalRebuildSum      int               `json:"total_rebuild_sum"`
}

type selectedVersionRow struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type candidateVersionRow struct {
	Version  string   `json:"version"`
	Revision int      `json:"revision"`
	Status   string   `json:"status"`
	Reasons  []string `json:"reasons"`
}

type instanceReport struct {
	InstanceRef       string                `json:"instance_ref"`
	ParentInstanceRef string                `json:"parent_instance_ref"`
	Name              string                `json:"name"`
	VersionRange      string                `json:"version_range"`
	RequiredFeatures  []string              `json:"required_features"`
	CandidateVersion  []candidateVersionRow `json:"candidate_versions"`
}

type candidateReport struct {
	RequestID       string               `json:"request_id"`
	SelectedVersion []selectedVersionRow `json:"selected_versions"`
	Instances       []instanceReport     `json:"instances"`
}

type fetchRow struct {
	FormulaName    string
	Platform       string
	Digest         string
	Bytes          int
	Cached         bool
	UsedByFormulae []string
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) != 7 ||
		args[0] != "plan" ||
		args[1] != "--catalog-root" ||
		args[3] != "--request" ||
		args[5] != "--out" ||
		!filepath.IsAbs(args[2]) ||
		!filepath.IsAbs(args[4]) ||
		!filepath.IsAbs(args[6]) {
		fmt.Fprintln(os.Stderr, usage)
		return 1
	}

	pl, err := loadPlanner(args[2], args[4])
	if err != nil {
		fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
		return 1
	}
	pl.search()
	if pl.Best == nil {
		fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
		return 1
	}

	planOut, fetchText, reportOut, err := pl.render()
	if err != nil {
		fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
		return 1
	}
	if !withinBudget(planOut, pl.Request) {
		fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
		return 1
	}
	if err := writeOutputs(args[6], planOut, fetchText, reportOut); err != nil {
		fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
		return 1
	}
	return 0
}

func loadPlanner(catalogRoot, requestPath string) (*planner, error) {
	var req requestFile
	if err := readJSON(requestPath, &req); err != nil {
		return nil, err
	}
	var catalog formulaCatalog
	if err := readJSON(filepath.Join(catalogRoot, "formula_catalog.json"), &catalog); err != nil {
		return nil, err
	}
	var policyFile platformPolicyFile
	if err := readJSON(filepath.Join(catalogRoot, "platform_policy.json"), &policyFile); err != nil {
		return nil, err
	}
	var mirrors mirrorInventory
	if err := readJSON(filepath.Join(catalogRoot, "mirror_inventory.json"), &mirrors); err != nil {
		return nil, err
	}

	formulae := map[string][]formulaChoice{}
	for _, record := range catalog.Formulas {
		versions := make([]formulaChoice, len(record.Versions))
		copy(versions, record.Versions)
		for i := range versions {
			versions[i].Name = record.Name
		}
		sort.Slice(versions, func(i, j int) bool {
			cmp := compareSemver(versions[i].Version, versions[j].Version)
			if cmp != 0 {
				return cmp > 0
			}
			return versions[i].Revision < versions[j].Revision
		})
		formulae[record.Name] = versions
	}

	policies := map[string]platformPolicy{}
	for _, row := range policyFile.Platforms {
		policies[row.Platform] = row
	}

	roots := map[string]rootRequest{}
	for _, root := range req.RootFormulae {
		features := dedupeSorted(root.RequiredFeature)
		root.RequiredFeature = features
		roots[root.Name] = root
	}

	mirrorSet := map[string]bool{}
	for _, digest := range mirrors.MirroredDigests {
		mirrorSet[digest] = true
	}

	return &planner{
		Request:       req,
		Policies:      policies,
		Mirrors:       mirrorSet,
		Formulae:      formulae,
		RootRequested: roots,
	}, nil
}

func (p *planner) search() {
	pending := make([]instance, 0, len(p.Request.RootFormulae))
	for _, root := range p.Request.RootFormulae {
		pending = append(pending, instance{
			Ref:          "root." + root.Name,
			ParentRef:    "NONE",
			Name:         root.Name,
			VersionRange: root.VersionRange,
			Required:     dedupeSorted(root.RequiredFeature),
			Root:         true,
			AllowKegOnly: root.AllowKegOnly,
		})
	}
	state := &searchState{Selected: map[string]formulaChoice{}}
	p.searchPending(pending, state)
}

func (p *planner) searchPending(pending []instance, state *searchState) {
	if len(pending) == 0 {
		if p.isFeasible(state.Selected) {
			candidate := &solution{
				Selected:  copySelected(state.Selected),
				Instances: append([]instance(nil), state.Instances...),
			}
			if p.Best == nil || p.compareSolutions(candidate, p.Best) < 0 {
				p.Best = candidate
			}
		}
		return
	}

	inst := pending[0]
	rest := pending[1:]
	snapshotLen := len(state.Instances)
	state.Instances = append(state.Instances, inst)

	if selected, ok := state.Selected[inst.Name]; ok {
		if len(p.localReasons(inst, selected)) == 0 {
			next := append(p.makeChildren(inst, selected), rest...)
			p.searchPending(next, state)
		}
		state.Instances = state.Instances[:snapshotLen]
		return
	}

	for _, candidate := range p.Formulae[inst.Name] {
		if len(p.localReasons(inst, candidate)) != 0 {
			continue
		}
		state.Selected[inst.Name] = candidate
		next := append(p.makeChildren(inst, candidate), rest...)
		p.searchPending(next, state)
		delete(state.Selected, inst.Name)
		state.Instances = state.Instances[:snapshotLen+1]
	}
	state.Instances = state.Instances[:snapshotLen]
}

func (p *planner) makeChildren(inst instance, version formulaChoice) []instance {
	children := []instance{}
	for _, dep := range version.Dependencies {
		if !containsAll(inst.Required, dep.RequiresFeatures) {
			continue
		}
		children = append(children, instance{
			Ref:          inst.Ref + "->" + dep.Name,
			ParentRef:    inst.Ref,
			Name:         dep.Name,
			VersionRange: dep.VersionRange,
			Required:     []string{},
			Root:         false,
			AllowKegOnly: true,
		})
	}
	return children
}

func (p *planner) localReasons(inst instance, version formulaChoice) []string {
	reasons := []string{}
	if !matchesRange(version.Version, inst.VersionRange) {
		reasons = append(reasons, "version_out_of_range")
	}
	if version.Prerelease && !p.Request.AllowPrerelease {
		reasons = append(reasons, "prerelease_blocked")
	}
	if inst.Root && !inst.AllowKegOnly && version.KegOnly {
		reasons = append(reasons, "keg_only_blocked")
	}
	if len(reasons) > 0 {
		return reasons
	}

	bottles := bottleMap(version.Bottles)
	missing := false
	runtimeConflict := false
	relocationConflict := false
	codesignMissing := false

	for _, platform := range p.Request.TargetPlatforms {
		bottle, ok := bottles[platform]
		if !ok {
			missing = true
			continue
		}
		policy := p.Policies[platform]
		if compareSemver(bottle.RuntimeFloor, policy.MinimumRuntime) > 0 {
			runtimeConflict = true
		}
		if p.Request.RelocationPolicy == "strict" && !bottle.Relocatable {
			relocationConflict = true
		}
		if policy.RequireCodesigned && !bottle.Codesigned {
			codesignMissing = true
		}
	}
	if missing {
		reasons = append(reasons, "platform_unavailable")
	}
	if runtimeConflict {
		reasons = append(reasons, "runtime_floor_conflict")
	}
	if relocationConflict {
		reasons = append(reasons, "relocation_conflict")
	}
	if codesignMissing {
		reasons = append(reasons, "codesign_missing")
	}
	return reasons
}

func (p *planner) isFeasible(selected map[string]formulaChoice) bool {
	plan, _, _, err := p.renderFromSolution(&solution{Selected: selected, Instances: nil})
	if err != nil {
		return false
	}
	return withinBudget(plan, p.Request)
}

func (p *planner) compareSolutions(left, right *solution) int {
	leftPlan, _, _, _ := p.renderFromSolution(left)
	rightPlan, _, _, _ := p.renderFromSolution(right)

	if leftPlan.UniqueNewDigestCount != rightPlan.UniqueNewDigestCount {
		return compareInt(leftPlan.UniqueNewDigestCount, rightPlan.UniqueNewDigestCount)
	}
	if leftPlan.TotalNewBytes != rightPlan.TotalNewBytes {
		return compareInt(leftPlan.TotalNewBytes, rightPlan.TotalNewBytes)
	}
	if leftPlan.TotalRebuildSum != rightPlan.TotalRebuildSum {
		return compareInt(leftPlan.TotalRebuildSum, rightPlan.TotalRebuildSum)
	}

	for _, root := range p.Request.RootFormulae {
		lv := left.Selected[root.Name].Version
		rv := right.Selected[root.Name].Version
		if cmp := compareSemver(lv, rv); cmp != 0 {
			return -cmp
		}
	}

	leftIDs := identityList(leftPlan.SelectedFormulae)
	rightIDs := identityList(rightPlan.SelectedFormulae)
	for i := 0; i < len(leftIDs) && i < len(rightIDs); i++ {
		if leftIDs[i] != rightIDs[i] {
			if leftIDs[i] < rightIDs[i] {
				return -1
			}
			return 1
		}
	}
	return compareInt(len(leftIDs), len(rightIDs))
}

func (p *planner) render() (*promotionPlan, string, *candidateReport, error) {
	return p.renderFromSolution(p.Best)
}

func (p *planner) renderFromSolution(sol *solution) (*promotionPlan, string, *candidateReport, error) {
	selectedNames := make([]string, 0, len(sol.Selected))
	for name := range sol.Selected {
		selectedNames = append(selectedNames, name)
	}
	sort.Strings(selectedNames)

	rootSelections := make([]rootSelection, 0, len(p.Request.RootFormulae))
	selectedFormulae := make([]selectedFormula, 0, len(selectedNames))
	fetchRows := map[string]*fetchRow{}
	digestSet := map[string]bool{}
	totalBytes := 0
	totalRebuild := 0

	for _, root := range p.Request.RootFormulae {
		selected, ok := sol.Selected[root.Name]
		if !ok {
			return nil, "", nil, fmt.Errorf("missing root selection")
		}
		rootSelections = append(rootSelections, rootSelection{Name: root.Name, SelectedVersion: selected.Version})
	}

	for _, name := range selectedNames {
		version := sol.Selected[name]
		root, isRoot := p.RootRequested[name]
		features := []string{}
		if isRoot {
			features = dedupeSorted(root.RequiredFeature)
		}
		bottleByPlatform := bottleMap(version.Bottles)
		outBottles := make([]bottleOutput, 0, len(p.Request.TargetPlatforms))
		for _, platform := range p.Request.TargetPlatforms {
			bottle, ok := bottleByPlatform[platform]
			if !ok {
				return nil, "", nil, fmt.Errorf("missing bottle")
			}
			cached := p.Mirrors[bottle.Digest]
			outBottles = append(outBottles, bottleOutput{
				Platform:     platform,
				Digest:       bottle.Digest,
				Cached:       cached,
				Bytes:        bottle.Bytes,
				Rebuild:      bottle.Rebuild,
				Relocatable:  bottle.Relocatable,
				Codesigned:   bottle.Codesigned,
				RuntimeFloor: bottle.RuntimeFloor,
			})
			user := name + "@" + platform
			row, ok := fetchRows[bottle.Digest]
			if !ok {
				fetchRows[bottle.Digest] = &fetchRow{
					FormulaName:    name,
					Platform:       platform,
					Digest:         bottle.Digest,
					Bytes:          bottle.Bytes,
					Cached:         cached,
					UsedByFormulae: []string{user},
				}
			} else {
				row.UsedByFormulae = append(row.UsedByFormulae, user)
				owner := row.FormulaName + "@" + row.Platform
				if user < owner {
					row.FormulaName = name
					row.Platform = platform
				}
			}
			if !cached && !digestSet[bottle.Digest] {
				totalBytes += bottle.Bytes
			}
			if !digestSet[bottle.Digest] {
				digestSet[bottle.Digest] = true
			}
			totalRebuild += bottle.Rebuild
		}
		deps := []dependencyOutput{}
		for _, dep := range version.Dependencies {
			if containsAll(features, dep.RequiresFeatures) {
				deps = append(deps, dependencyOutput{
					Name:             dep.Name,
					VersionRange:     dep.VersionRange,
					RequiresFeatures: append([]string{}, dep.RequiresFeatures...),
				})
			}
		}
		selectedFormulae = append(selectedFormulae, selectedFormula{
			Name:          name,
			Version:       version.Version,
			Revision:      version.Revision,
			ActiveFeature: features,
			RootRequested: isRoot,
			Dependencies:  deps,
			Bottles:       outBottles,
		})
	}

	newDigestCount := 0
	fetchList := make([]fetchRow, 0, len(fetchRows))
	for _, row := range fetchRows {
		sort.Strings(row.UsedByFormulae)
		fetchList = append(fetchList, *row)
		if !row.Cached {
			newDigestCount++
		}
	}

	plan := &promotionPlan{
		RequestID:            p.Request.RequestID,
		RelocationPolicy:     p.Request.RelocationPolicy,
		TargetPlatforms:      append([]string(nil), p.Request.TargetPlatforms...),
		RootSelections:       rootSelections,
		SelectedFormulae:     selectedFormulae,
		UniqueNewDigestCount: newDigestCount,
		TotalNewBytes:        totalBytes,
		TotalRebuildSum:      totalRebuild,
	}

	report := &candidateReport{
		RequestID:       p.Request.RequestID,
		SelectedVersion: []selectedVersionRow{},
		Instances:       []instanceReport{},
	}
	for _, name := range selectedNames {
		report.SelectedVersion = append(report.SelectedVersion, selectedVersionRow{Name: name, Version: sol.Selected[name].Version})
	}
	for _, inst := range sol.Instances {
		row := instanceReport{
			InstanceRef:       inst.Ref,
			ParentInstanceRef: inst.ParentRef,
			Name:              inst.Name,
			VersionRange:      inst.VersionRange,
			RequiredFeatures:  append([]string{}, inst.Required...),
			CandidateVersion:  []candidateVersionRow{},
		}
		for _, candidate := range p.Formulae[inst.Name] {
			reasons := p.localReasons(inst, candidate)
			status := "eligible_not_chosen"
			if len(reasons) > 0 {
				status = "rejected_gate"
			} else if sol.Selected[inst.Name].Version == candidate.Version && sol.Selected[inst.Name].Revision == candidate.Revision {
				status = "selected"
			}
			row.CandidateVersion = append(row.CandidateVersion, candidateVersionRow{
				Version:  candidate.Version,
				Revision: candidate.Revision,
				Status:   status,
				Reasons:  reasons,
			})
		}
		report.Instances = append(report.Instances, row)
	}

	sort.Slice(fetchList, func(i, j int) bool {
		if fetchList[i].Cached != fetchList[j].Cached {
			return !fetchList[i].Cached
		}
		if fetchList[i].FormulaName != fetchList[j].FormulaName {
			return fetchList[i].FormulaName < fetchList[j].FormulaName
		}
		if fetchList[i].Platform != fetchList[j].Platform {
			return fetchList[i].Platform < fetchList[j].Platform
		}
		return fetchList[i].Digest < fetchList[j].Digest
	})

	var builder strings.Builder
	builder.WriteString("step\taction\tdigest\tformula_name\tplatform\tbytes\tcached\tused_by_formulae\n")
	for i, row := range fetchList {
		action := "fetch"
		if row.Cached {
			action = "reuse_mirrored"
		}
		builder.WriteString(fmt.Sprintf("%d\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n",
			i+1,
			action,
			row.Digest,
			row.FormulaName,
			row.Platform,
			row.Bytes,
			strconv.FormatBool(row.Cached),
			strings.Join(row.UsedByFormulae, ","),
		))
	}

	return plan, builder.String(), report, nil
}

func withinBudget(plan *promotionPlan, req requestFile) bool {
	return plan.UniqueNewDigestCount <= req.MaxNewDigests && plan.TotalNewBytes <= req.MaxNewBytes
}

func writeOutputs(outDir string, plan *promotionPlan, fetchText string, report *candidateReport) error {
	if err := os.RemoveAll(outDir); err != nil {
		return err
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	planBytes, err := compactJSON(plan)
	if err != nil {
		return err
	}
	reportBytes, err := compactJSON(report)
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "promotion_plan.json"), planBytes, 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "mirror_fetch.tsv"), []byte(fetchText), 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "candidate_report.json"), reportBytes, 0o644); err != nil {
		return err
	}
	return nil
}

func compactJSON(value interface{}) ([]byte, error) {
	var buf bytes.Buffer
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func readJSON(path string, target interface{}) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, target)
}

func bottleMap(bottles []bottleChoice) map[string]bottleChoice {
	result := map[string]bottleChoice{}
	for _, bottle := range bottles {
		result[bottle.Platform] = bottle
	}
	return result
}

func dedupeSorted(values []string) []string {
	seen := map[string]bool{}
	result := []string{}
	for _, value := range values {
		if !seen[value] {
			seen[value] = true
			result = append(result, value)
		}
	}
	sort.Strings(result)
	return result
}

func containsAll(values, required []string) bool {
	set := map[string]bool{}
	for _, value := range values {
		set[value] = true
	}
	for _, need := range required {
		if !set[need] {
			return false
		}
	}
	return true
}

func copySelected(src map[string]formulaChoice) map[string]formulaChoice {
	dst := map[string]formulaChoice{}
	for key, value := range src {
		dst[key] = value
	}
	return dst
}

func compareInt(left, right int) int {
	if left < right {
		return -1
	}
	if left > right {
		return 1
	}
	return 0
}

func identityList(rows []selectedFormula) []string {
	result := []string{}
	for _, row := range rows {
		for _, bottle := range row.Bottles {
			result = append(result, fmt.Sprintf("formula/%s/%s/%s@%s", row.Name, row.Version, bottle.Platform, bottle.Digest))
		}
	}
	sort.Strings(result)
	return result
}

type parsedVersion struct {
	Parts      []int
	Prerelease string
}

func parseVersion(raw string) parsedVersion {
	main := raw
	pre := ""
	if strings.Contains(raw, "-") {
		pieces := strings.SplitN(raw, "-", 2)
		main = pieces[0]
		pre = pieces[1]
	}
	partStrings := strings.Split(main, ".")
	parts := make([]int, len(partStrings))
	for i, piece := range partStrings {
		value, _ := strconv.Atoi(piece)
		parts[i] = value
	}
	return parsedVersion{Parts: parts, Prerelease: pre}
}

func compareSemver(left, right string) int {
	lv := parseVersion(left)
	rv := parseVersion(right)
	maxLen := len(lv.Parts)
	if len(rv.Parts) > maxLen {
		maxLen = len(rv.Parts)
	}
	for i := 0; i < maxLen; i++ {
		li := 0
		ri := 0
		if i < len(lv.Parts) {
			li = lv.Parts[i]
		}
		if i < len(rv.Parts) {
			ri = rv.Parts[i]
		}
		if li < ri {
			return -1
		}
		if li > ri {
			return 1
		}
	}
	if lv.Prerelease == rv.Prerelease {
		return 0
	}
	if lv.Prerelease == "" {
		return 1
	}
	if rv.Prerelease == "" {
		return -1
	}
	if lv.Prerelease < rv.Prerelease {
		return -1
	}
	if lv.Prerelease > rv.Prerelease {
		return 1
	}
	return 0
}

func matchesRange(version, rawRange string) bool {
	fields := strings.Fields(rawRange)
	if len(fields) != 2 {
		return false
	}
	lowerOp, lowerVer := splitComparator(fields[0])
	upperOp, upperVer := splitComparator(fields[1])
	if !compareOp(compareSemver(version, lowerVer), lowerOp) {
		return false
	}
	return compareOp(compareSemver(version, upperVer), upperOp)
}

func splitComparator(raw string) (string, string) {
	if strings.HasPrefix(raw, ">=") {
		return ">=", strings.TrimPrefix(raw, ">=")
	}
	if strings.HasPrefix(raw, "<=") {
		return "<=", strings.TrimPrefix(raw, "<=")
	}
	if strings.HasPrefix(raw, ">") {
		return ">", strings.TrimPrefix(raw, ">")
	}
	if strings.HasPrefix(raw, "<") {
		return "<", strings.TrimPrefix(raw, "<")
	}
	if strings.HasPrefix(raw, "=") {
		return "=", strings.TrimPrefix(raw, "=")
	}
	return "", raw
}

func compareOp(result int, op string) bool {
	switch op {
	case ">=":
		return result >= 0
	case "<=":
		return result <= 0
	case ">":
		return result > 0
	case "<":
		return result < 0
	case "=":
		return result == 0
	default:
		return false
	}
}
