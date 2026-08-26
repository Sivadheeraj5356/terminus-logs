package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"
)

type indexFile struct {
	Packages map[string][]pkgVersion `json:"packages"`
}
type pkgVersion struct {
	Version      string              `json:"version"`
	Yanked       bool                `json:"yanked,omitempty"`
	Features     map[string][]string `json:"features,omitempty"`
	Dependencies []dependency        `json:"dependencies,omitempty"`
	Conflicts    []conflict          `json:"conflicts,omitempty"`
}
type dependency struct {
	Name            string   `json:"name"`
	Constraint      string   `json:"constraint"`
	Features        []string `json:"features,omitempty"`
	Optional        bool     `json:"optional,omitempty"`
	DefaultFeatures *bool    `json:"default_features,omitempty"`
	Targets         []string `json:"targets,omitempty"`
	WhenFeatures    []string `json:"when_features,omitempty"`
}
type conflict struct {
	Name, Constraint string
	Targets          []string `json:"targets,omitempty"`
}

func (c *conflict) UnmarshalJSON(data []byte) error {
	type wire struct {
		Name       string   `json:"name"`
		Constraint string   `json:"constraint"`
		Targets    []string `json:"targets"`
	}
	var w wire
	if err := json.Unmarshal(data, &w); err != nil {
		return err
	}
	c.Name, c.Constraint, c.Targets = w.Name, w.Constraint, w.Targets
	return nil
}

type projectFile struct {
	Target  string            `json:"target"`
	Roots   []rootDep         `json:"roots"`
	Patches map[string]string `json:"patches,omitempty"`
}
type rootDep struct {
	Name            string   `json:"name"`
	Constraint      string   `json:"constraint"`
	Features        []string `json:"features,omitempty"`
	DefaultFeatures *bool    `json:"default_features,omitempty"`
}
type semver struct{ major, minor, patch string }
type pkgReport struct {
	Name         string   `json:"name"`
	Version      string   `json:"version"`
	Direct       bool     `json:"direct"`
	Features     []string `json:"features"`
	Dependencies []string `json:"dependencies"`
}
type report struct {
	Status     string      `json:"status"`
	Packages   []pkgReport `json:"packages"`
	BuildOrder []string    `json:"build_order"`
	Problems   []string    `json:"problems"`
}
type closureState struct {
	constraints, requests map[string]map[string]bool
	deps                  map[string][]string
	problems              map[string]bool
}
type solvedState struct {
	selected map[string]pkgVersion
	closure  closureState
	order    []string
}

func main() {
	indexPath := flag.String("index", "", "package index path")
	projectPath := flag.String("project", "", "project manifest path")
	outPath := flag.String("out", "", "lock report output path")
	flag.Parse()
	if *indexPath == "" || *projectPath == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "usage: depotlock --index INDEX --project PROJECT --out OUT")
		os.Exit(2)
	}
	var idx indexFile
	var project projectFile
	if err := readJSON(*indexPath, &idx); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := readJSON(*projectPath, &project); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := json.MarshalIndent(resolve(idx, project), "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(*outPath, append(data, '\n'), 0644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func readJSON(path string, value any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, value)
}

func resolve(idx indexFile, project projectFile) report {
	var answer *solvedState
	solved, problems := search(idx, project, map[string]pkgVersion{}, &answer)
	if !solved {
		return report{"conflict", []pkgReport{}, []string{}, sortedKeys(problems)}
	}
	direct := map[string]bool{}
	for _, root := range project.Roots {
		direct[root.Name] = true
	}
	rows := []pkgReport{}
	for _, name := range sortedPkgKeys(answer.selected) {
		rows = append(rows, pkgReport{name, answer.selected[name].Version, direct[name], sortedKeys(answer.closure.requests[name]), answer.closure.deps[name]})
	}
	return report{"ok", rows, answer.order, []string{}}
}

func search(idx indexFile, project projectFile, selected map[string]pkgVersion, answer **solvedState) (bool, map[string]bool) {
	state := computeClosure(project, selected)
	reject := copySet(state.problems)
	for name, pv := range selected {
		if state.constraints[name] == nil {
			continue
		}
		valid := false
		for _, candidate := range candidates(idx, project, name, state.constraints[name]) {
			if candidate.Version == pv.Version {
				valid = true
				break
			}
		}
		if !valid {
			reject["no-version:"+name] = true
		}
	}
	for reason := range conflictProblems(selected, project.Target) {
		reject[reason] = true
	}
	if len(reject) != 0 {
		return false, reject
	}

	unresolved := []string{}
	for name := range state.constraints {
		if _, ok := selected[name]; !ok {
			unresolved = append(unresolved, name)
		}
	}
	sort.Strings(unresolved)
	if len(unresolved) != 0 {
		name := unresolved[0]
		versions, exists := idx.Packages[name]
		if !exists {
			return false, setOf("missing-package:"+name, "no-version:"+name)
		}
		_ = versions
		choices := candidates(idx, project, name, state.constraints[name])
		if len(choices) == 0 {
			return false, setOf("no-version:" + name)
		}
		allProblems := map[string]bool{}
		anySolved := false
		for _, choice := range choices {
			next := copySelected(selected)
			next[name] = choice
			ok, branchProblems := search(idx, project, next, answer)
			if ok {
				anySolved = true
				continue
			}
			for problem := range branchProblems {
				allProblems[problem] = true
			}
		}
		if anySolved {
			return true, map[string]bool{}
		}
		return false, allProblems
	}

	order, cycleProblems := topo(selected, state.deps)
	if len(cycleProblems) != 0 {
		return false, cycleProblems
	}
	if *answer == nil || assignmentPreferred(idx, project, selected, (*answer).selected) {
		*answer = &solvedState{copySelected(selected), state, order}
	}
	return true, map[string]bool{}
}

func assignmentPreferred(idx indexFile, project projectFile, candidate, incumbent map[string]pkgVersion) bool {
	rootNames := map[string]bool{}
	for _, root := range project.Roots {
		rootNames[root.Name] = true
	}
	priority := sortedKeys(rootNames)
	for _, name := range sortedIndexKeys(idx.Packages) {
		if !rootNames[name] {
			priority = append(priority, name)
		}
	}
	for _, name := range priority {
		left, leftOK := candidate[name]
		right, rightOK := incumbent[name]
		if leftOK != rightOK {
			return leftOK
		}
		if leftOK {
			if cmp := compareVersionString(left.Version, right.Version); cmp != 0 {
				return cmp > 0
			}
		}
	}
	return false
}

func computeClosure(project projectFile, selected map[string]pkgVersion) closureState {
	state := closureState{map[string]map[string]bool{}, map[string]map[string]bool{}, map[string][]string{}, map[string]bool{}}
	for _, root := range project.Roots {
		add(state.constraints, root.Name, root.Constraint)
		if defaultOn(root.DefaultFeatures) {
			add(state.requests, root.Name, "default")
		}
		for _, feature := range root.Features {
			add(state.requests, root.Name, feature)
		}
	}
	for changed := true; changed; {
		changed = false
		for _, name := range sortedPkgKeys(selected) {
			if state.constraints[name] == nil {
				continue
			}
			expanded, activated, problems := expandFeatures(name, selected[name], state.requests[name])
			for problem := range problems {
				state.problems[problem] = true
			}
			for feature := range expanded {
				if add(state.requests, name, feature) {
					changed = true
				}
			}
			depNames := map[string]bool{}
			for _, dep := range selected[name].Dependencies {
				if !targetMatches(dep.Targets, project.Target) || !containsAll(expanded, dep.WhenFeatures) || (dep.Optional && !activated[dep.Name]) {
					continue
				}
				depNames[dep.Name] = true
				if add(state.constraints, dep.Name, dep.Constraint) {
					changed = true
				}
				if defaultOn(dep.DefaultFeatures) && add(state.requests, dep.Name, "default") {
					changed = true
				}
				for _, feature := range dep.Features {
					if add(state.requests, dep.Name, feature) {
						changed = true
					}
				}
			}
			state.deps[name] = sortedKeys(depNames)
		}
	}
	return state
}

func expandFeatures(name string, pv pkgVersion, requested map[string]bool) (map[string]bool, map[string]bool, map[string]bool) {
	expanded, activated, problems := map[string]bool{}, map[string]bool{}, map[string]bool{}
	queue := sortedKeys(requested)
	for len(queue) != 0 {
		feature := queue[0]
		queue = queue[1:]
		if expanded[feature] {
			continue
		}
		atoms, exists := pv.Features[feature]
		if !exists {
			problems["missing-feature:"+name+":"+feature] = true
			continue
		}
		expanded[feature] = true
		for _, atom := range atoms {
			if strings.HasPrefix(atom, "dep:") {
				activated[strings.TrimPrefix(atom, "dep:")] = true
			} else if !expanded[atom] {
				queue = append(queue, atom)
				sort.Strings(queue)
			}
		}
	}
	return expanded, activated, problems
}

func candidates(idx indexFile, project projectFile, name string, constraints map[string]bool) []pkgVersion {
	patch := project.Patches[name]
	choices := []pkgVersion{}
	for _, pv := range idx.Packages[name] {
		if patch != "" && pv.Version != patch {
			continue
		}
		if patch == "" && pv.Yanked {
			continue
		}
		if satisfiesAll(pv.Version, constraints) {
			choices = append(choices, pv)
		}
	}
	sort.Slice(choices, func(i, j int) bool { return compareVersionString(choices[i].Version, choices[j].Version) > 0 })
	return choices
}

func conflictProblems(selected map[string]pkgVersion, target string) map[string]bool {
	problems := map[string]bool{}
	for owner, pv := range selected {
		for _, item := range pv.Conflicts {
			other, exists := selected[item.Name]
			if !exists || !targetMatches(item.Targets, target) || !satisfies(other.Version, item.Constraint) {
				continue
			}
			left, right := owner+"@"+pv.Version, item.Name+"@"+other.Version
			if left > right {
				left, right = right, left
			}
			problems["incompatible:"+left+":"+right] = true
		}
	}
	return problems
}

func topo(selected map[string]pkgVersion, deps map[string][]string) ([]string, map[string]bool) {
	remaining, built := map[string]bool{}, map[string]bool{}
	for name := range selected {
		remaining[name] = true
	}
	order := []string{}
	for len(remaining) != 0 {
		ready := []string{}
		for name := range remaining {
			ok := true
			for _, dep := range deps[name] {
				if _, selectedDep := selected[dep]; selectedDep && !built[dep] {
					ok = false
					break
				}
			}
			if ok {
				ready = append(ready, name)
			}
		}
		if len(ready) == 0 {
			problems := map[string]bool{}
			for name := range remaining {
				problems["cycle:"+name] = true
			}
			return []string{}, problems
		}
		sort.Strings(ready)
		chosen := ready[0]
		delete(remaining, chosen)
		built[chosen] = true
		order = append(order, chosen)
	}
	return order, map[string]bool{}
}

func satisfiesAll(raw string, constraints map[string]bool) bool {
	for constraint := range constraints {
		if !satisfies(raw, constraint) {
			return false
		}
	}
	return true
}
func satisfies(raw, constraint string) bool {
	constraint = strings.TrimSpace(constraint)
	if constraint == "" || constraint == "*" {
		return true
	}
	for _, term := range strings.Split(constraint, ",") {
		term = strings.TrimSpace(term)
		if term == "" || term == "*" {
			continue
		}
		if strings.HasPrefix(term, "^") {
			if !satisfiesCaret(raw, strings.TrimSpace(term[1:])) {
				return false
			}
			continue
		}
		op, value := "", term
		for _, candidate := range []string{">=", "<=", ">", "<"} {
			if strings.HasPrefix(term, candidate) {
				op, value = candidate, strings.TrimSpace(term[len(candidate):])
				break
			}
		}
		cmp := compareVersionString(raw, value)
		if (op == "" && cmp != 0) || (op == ">=" && cmp < 0) || (op == ">" && cmp <= 0) || (op == "<=" && cmp > 0) || (op == "<" && cmp >= 0) {
			return false
		}
	}
	return true
}
func satisfiesCaret(raw, base string) bool {
	got, low := parseVersion(raw), parseVersion(base)
	if compareVersion(got, low) < 0 {
		return false
	}
	if low.major != "0" {
		return got.major == low.major
	}
	if low.minor != "0" {
		return got.major == "0" && got.minor == low.minor
	}
	return got.major == "0" && got.minor == "0" && got.patch == low.patch
}
func parseVersion(raw string) semver {
	parts := strings.Split(raw, ".")
	if len(parts) != 3 {
		panic("invalid version: " + raw)
	}
	nums := [3]string{}
	for i, part := range parts {
		if part == "" {
			panic("invalid version: " + raw)
		}
		for _, digit := range []byte(part) {
			if digit < '0' || digit > '9' {
				panic("invalid version: " + raw)
			}
		}
		nums[i] = strings.TrimLeft(part, "0")
		if nums[i] == "" {
			nums[i] = "0"
		}
	}
	return semver{nums[0], nums[1], nums[2]}
}
func compareVersionString(a, b string) int { return compareVersion(parseVersion(a), parseVersion(b)) }
func compareVersion(a, b semver) int {
	if a.major != b.major {
		return compareComponent(a.major, b.major)
	}
	if a.minor != b.minor {
		return compareComponent(a.minor, b.minor)
	}
	return compareComponent(a.patch, b.patch)
}
func compareComponent(a, b string) int {
	if len(a) < len(b) {
		return -1
	}
	if len(a) > len(b) {
		return 1
	}
	if a < b {
		return -1
	}
	if a > b {
		return 1
	}
	return 0
}
func targetMatches(targets []string, target string) bool {
	if len(targets) == 0 {
		return true
	}
	for _, item := range targets {
		if item == "*" || item == target {
			return true
		}
	}
	return false
}
func defaultOn(value *bool) bool { return value == nil || *value }
func containsAll(set map[string]bool, values []string) bool {
	for _, value := range values {
		if !set[value] {
			return false
		}
	}
	return true
}
func add(sets map[string]map[string]bool, key, value string) bool {
	if sets[key] == nil {
		sets[key] = map[string]bool{}
	}
	if sets[key][value] {
		return false
	}
	sets[key][value] = true
	return true
}
func sortedKeys(set map[string]bool) []string {
	out := []string{}
	for key := range set {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}
func sortedPkgKeys(set map[string]pkgVersion) []string {
	out := []string{}
	for key := range set {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}
func sortedIndexKeys(set map[string][]pkgVersion) []string {
	out := []string{}
	for key := range set {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}
func copySet(input map[string]bool) map[string]bool {
	out := map[string]bool{}
	for key := range input {
		out[key] = true
	}
	return out
}
func setOf(values ...string) map[string]bool {
	out := map[string]bool{}
	for _, value := range values {
		out[value] = true
	}
	return out
}
func copySelected(input map[string]pkgVersion) map[string]pkgVersion {
	out := map[string]pkgVersion{}
	for key, value := range input {
		out[key] = value
	}
	return out
}
