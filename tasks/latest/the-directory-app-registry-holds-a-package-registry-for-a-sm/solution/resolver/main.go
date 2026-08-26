// SOURCE: dependency resolution as bounded constraint search (verify is
// polynomial, find is exponential; Di Cosmo 2005 reduces package resolution
// to SAT).
//
// GRAFO: dispatchctl and fleetbilling are the two root packages. Every
// fleetbilling release pins wiretype to exactly 1.0.0, so wiretype is fixed
// the moment any fleetbilling version is chosen, regardless of which one.
// dispatchctl's newest release wants wiretype 2.0.0, which collides with
// that pin, so dispatchctl has to drop to its next release. That release's
// routectl floor admits routectl's newest release too, which both wants
// wiretype 2.0.0 again and separately conflicts with the ratesync floor
// fleetbilling's newest release carries, so routectl has to drop as well,
// to the release whose fleetauth floor reaches fleetauth's newest release.
// That release also pulls credstore, whose only release conflicts with
// telemetrybus at or above 3.0.0; fleetauth's own quotacap floor forces
// quotacap 2.0.0, and quotacap 2.0.0 forces telemetrybus straight into that
// conflicting range, so the credstore collision only surfaces after
// quotacap and telemetrybus are both committed, three packages downstream
// of the fleetauth choice that caused it. A resolver that only ever
// rechecks the package it just picked (or the one immediately before it in
// the search) never revisits fleetauth once it has moved on to quotacap
// and telemetrybus, so it needs genuine chronological backtracking all the
// way back up to fleetauth's own candidate list, not just a retry of
// whichever package's own range failed to match, to land on fleetauth's
// next release instead, which does not pull credstore at all. quotacap's
// two lower releases each conflict with wiretype at exactly 1.0.0, the
// version wiretype is already pinned to, so every quotacap release below
// 2.0.0 is unreachable no matter which fleetauth or fleetbilling release is
// in play, independent of the credstore trap. Three unrelated packages
// (alertagg/alertfeed, backoffpolicy/backoffcore, snapreader/snapwriter)
// each carry one more independent trap of the same shallow shape: their
// newest releases conflict with each other, so one side of each pair has to
// drop even though nothing else in the graph touches it.
//
// CARET SEMANTICS (R2): the manifest constrains the two root packages with
// the caret operator, and R2 defines "^X.Y.Z" as "same minor, major floats
// upward" (minor==Y and major>=X, patch unconstrained), which is the
// reverse of the same-major reading carried by most real ecosystems.
// dispatchctl ships a 2.1.0 release and fleetbilling a 1.1.0 release; both
// are the numerically highest entry a same-major reading of the caret would
// grab first, and both have minor 1, so neither is in range under R2. The
// matches() method below implements R2 literally (minor equality with a
// floating major), so candidateVersions never offers 2.1.0 or 1.1.0 for the
// caret-bound roots and the search never has to reject them; the correct
// roots stay dispatchctl 2.0.4 (dropped from 3.0.0 by the wiretype pin) and
// fleetbilling 2.0.0 (a higher major than requested, which the floating-
// major caret admits). A resolver that hard-codes the same-major caret
// instead assigns 2.1.0 and 1.1.0, finishes with a complete, locally
// consistent lockfile, and is under-resolved on the root requirements
// themselves with no conflict anywhere to signal the miss.
//
// This resolver treats every package name pending a version as a variable
// and every requires/conflicts entry as a constraint, and searches for an
// assignment the same way a DPLL SAT solver searches for a satisfying
// assignment: pick the next pending variable in canonical order, try its
// candidate versions from newest to oldest under the local range semantics,
// propagate whatever new plain requirements that choice adds (narrowing or
// immediately rejecting other packages' candidate sets), and backtrack
// chronologically the moment a candidate can be proven inconsistent, either
// through a violated range, a violated conflict, or a requires target that
// is already pinned to something incompatible. A resolver that instead
// commits to the highest matching version per package independently,
// without ever undoing a choice once made, reaches dispatchctl's newest
// release, then fleetbilling's, and only then discovers the wiretype
// collision with no way to revisit the first pick: that is exactly the
// property this instance is built to have, and it repeats deeper in the
// graph at routectl and again at quotacap.
//
// R11: this program is the resolver contract RULES.md's R11 describes. It
// takes a registry directory, a manifest path, and an output path as its
// three positional arguments and performs only the resolution R1-R6
// specify, against whatever registry and manifest it is given, never
// against a path or package name baked in here. writeadapter.go (a
// separate program, built and run separately) reads whatever lock.json
// this one wrote and handles R7 on its own.
//
// Build: go build -o /tmp/resolver ./resolver (from /app/project, or from
// this directory directly).
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// ---------- versions ----------

type version struct {
	major, minor, patch int
}

func (v version) String() string {
	return fmt.Sprintf("%d.%d.%d", v.major, v.minor, v.patch)
}

func lessVersion(a, b version) bool {
	if a.major != b.major {
		return a.major < b.major
	}
	if a.minor != b.minor {
		return a.minor < b.minor
	}
	return a.patch < b.patch
}

func parseVersion(s string) (version, error) {
	parts := strings.Split(s, ".")
	if len(parts) != 3 {
		return version{}, fmt.Errorf("bad version %q", s)
	}
	nums := make([]int, 3)
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil {
			return version{}, fmt.Errorf("bad version %q: %w", s, err)
		}
		nums[i] = n
	}
	return version{nums[0], nums[1], nums[2]}, nil
}

// a range is one operator ("=", ">=", "^") applied to one version.
type verRange struct {
	op string
	v  version
}

func parseRange(s string) (verRange, error) {
	switch {
	case strings.HasPrefix(s, ">="):
		v, err := parseVersion(s[2:])
		return verRange{">=", v}, err
	case strings.HasPrefix(s, "^"):
		v, err := parseVersion(s[1:])
		return verRange{"^", v}, err
	case strings.HasPrefix(s, "="):
		v, err := parseVersion(s[1:])
		return verRange{"=", v}, err
	default:
		return verRange{}, fmt.Errorf("bad range %q", s)
	}
}

func (r verRange) matches(c version) bool {
	switch r.op {
	case "=":
		return c == r.v
	case ">=":
		if c.major != r.v.major {
			return c.major > r.v.major
		}
		if c.minor != r.v.minor {
			return c.minor > r.v.minor
		}
		return c.patch >= r.v.patch
	case "^":
		return c.minor == r.v.minor && c.major >= r.v.major
	}
	return false
}

// ---------- registry ----------

type plainReq struct {
	Package string `json:"package"`
	Range   string `json:"range"`
}

type reqEntry struct {
	Package string     `json:"package,omitempty"`
	Range   string     `json:"range,omitempty"`
	AnyOf   []plainReq `json:"any_of,omitempty"`
}

type pkgIndex struct {
	Name      string     `json:"name"`
	Version   string     `json:"version"`
	Requires  []reqEntry `json:"requires"`
	Conflicts []plainReq `json:"conflicts"`
}

type registry struct {
	byPkg          map[string]map[string]pkgIndex
	sortedVersions map[string][]version
}

func loadRegistry(root string) (*registry, error) {
	reg := &registry{
		byPkg:          map[string]map[string]pkgIndex{},
		sortedVersions: map[string][]version{},
	}
	pkgDirs, err := os.ReadDir(root)
	if err != nil {
		return nil, err
	}
	names := make([]string, 0, len(pkgDirs))
	for _, d := range pkgDirs {
		if d.IsDir() {
			names = append(names, d.Name())
		}
	}
	sort.Strings(names)
	for _, pkg := range names {
		verDirs, err := os.ReadDir(filepath.Join(root, pkg))
		if err != nil {
			return nil, err
		}
		vnames := make([]string, 0, len(verDirs))
		for _, d := range verDirs {
			if d.IsDir() {
				vnames = append(vnames, d.Name())
			}
		}
		sort.Strings(vnames)
		reg.byPkg[pkg] = map[string]pkgIndex{}
		versions := make([]version, 0, len(vnames))
		for _, vs := range vnames {
			raw, err := os.ReadFile(filepath.Join(root, pkg, vs, "index.json"))
			if err != nil {
				return nil, err
			}
			var idx pkgIndex
			if err := json.Unmarshal(raw, &idx); err != nil {
				return nil, fmt.Errorf("%s/%s: %w", pkg, vs, err)
			}
			reg.byPkg[pkg][vs] = idx
			v, err := parseVersion(vs)
			if err != nil {
				return nil, err
			}
			versions = append(versions, v)
		}
		sort.Slice(versions, func(i, j int) bool { return lessVersion(versions[j], versions[i]) })
		reg.sortedVersions[pkg] = versions
	}
	return reg, nil
}

// ---------- manifest.toml (fixed shape: [package] then repeated [[requires]]) ----------

func loadManifestRequires(path string) ([]plainReq, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var out []plainReq
	var cur *plainReq
	inRequires := false
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if line == "[[requires]]" {
			if cur != nil {
				out = append(out, *cur)
			}
			cur = &plainReq{}
			inRequires = true
			continue
		}
		if strings.HasPrefix(line, "[") {
			inRequires = false
			continue
		}
		if !inRequires || cur == nil {
			continue
		}
		eq := strings.Index(line, "=")
		if eq < 0 {
			continue
		}
		key := strings.TrimSpace(line[:eq])
		val := strings.TrimSpace(line[eq+1:])
		val = strings.Trim(val, "\"")
		switch key {
		case "package":
			cur.Package = val
		case "range":
			cur.Range = val
		}
	}
	if cur != nil {
		out = append(out, *cur)
	}
	return out, scanner.Err()
}

// ---------- solver ----------

// A worklist item is either a pending package (pkg set, anyOf nil) awaiting
// a version choice, or a pending any_of group (anyOf set, pkg empty)
// awaiting a choice of which listed alternative satisfies it.
type worklistItem struct {
	pkg   string
	anyOf []plainReq
}

type solverState struct {
	reg       *registry
	assigned  map[string]version
	ranges    map[string][]verRange
	worklist  []worklistItem
	scheduled map[string]bool
}

func cloneAssigned(m map[string]version) map[string]version {
	out := make(map[string]version, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

func cloneRanges(m map[string][]verRange) map[string][]verRange {
	out := make(map[string][]verRange, len(m))
	for k, v := range m {
		cp := make([]verRange, len(v))
		copy(cp, v)
		out[k] = cp
	}
	return out
}

func cloneScheduled(m map[string]bool) map[string]bool {
	out := make(map[string]bool, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

// conflictsWithAssigned reports whether assigning pkg=v would violate a
// conflicts declaration on either side, checked against every already
// assigned package (R3: the declaration can live on either package).
func conflictsWithAssigned(reg *registry, pkg string, v version, assigned map[string]version) bool {
	self := reg.byPkg[pkg][v.String()]
	for _, c := range self.Conflicts {
		if av, ok := assigned[c.Package]; ok {
			r, err := parseRange(c.Range)
			if err == nil && r.matches(av) {
				return true
			}
		}
	}
	for otherPkg, otherVer := range assigned {
		otherIdx := reg.byPkg[otherPkg][otherVer.String()]
		for _, c := range otherIdx.Conflicts {
			if c.Package == pkg {
				r, err := parseRange(c.Range)
				if err == nil && r.matches(v) {
					return true
				}
			}
		}
	}
	return false
}

// candidateVersions returns pkg's registry versions, newest first, that
// satisfy every range constraint accumulated for pkg so far.
func candidateVersions(reg *registry, pkg string, rs []verRange) []version {
	var out []version
	for _, v := range reg.sortedVersions[pkg] {
		ok := true
		for _, r := range rs {
			if !r.matches(v) {
				ok = false
				break
			}
		}
		if ok {
			out = append(out, v)
		}
	}
	return out
}

// anyOfSatisfied reports whether at least one alternative already holds
// against the current assignment. It returns (satisfied, decidable): a
// group is decidable once every package it names has been assigned.
func anyOfSatisfied(alts []plainReq, assigned map[string]version) (bool, bool) {
	decidable := true
	for _, a := range alts {
		av, ok := assigned[a.Package]
		if !ok {
			decidable = false
			continue
		}
		r, err := parseRange(a.Range)
		if err == nil && r.matches(av) {
			return true, true
		}
	}
	return false, decidable
}

// solve performs chronological backtracking search over the pending
// worklist, where each item is either a package awaiting a version choice
// or an any_of group awaiting a choice of which alternative satisfies it.
// idx is the next unresolved position.
func solve(idx int, st *solverState) map[string]version {
	if idx == len(st.worklist) {
		return st.assigned
	}

	item := st.worklist[idx]
	if item.anyOf != nil {
		return solveAnyOf(idx, item.anyOf, st)
	}
	return solvePackage(idx, item.pkg, st)
}

// solveAnyOf resolves one any_of group. If some already-assigned package
// already satisfies it, no choice is needed. Otherwise it branches over the
// listed alternatives in order: an alternative whose package is already
// assigned to an incompatible version cannot be pursued; an unassigned
// alternative is scheduled as a new pending package (exactly as a plain
// requirement would be) and the search recurses into it before the rest of
// the worklist, backtracking to the next alternative on failure.
func solveAnyOf(idx int, alts []plainReq, st *solverState) map[string]version {
	if ok, _ := anyOfSatisfied(alts, st.assigned); ok {
		return solve(idx+1, st)
	}

	for _, alt := range alts {
		r, err := parseRange(alt.Range)
		if err != nil {
			continue
		}

		if av, already := st.assigned[alt.Package]; already {
			if !r.matches(av) {
				continue
			}
			if result := solve(idx+1, st); result != nil {
				return result
			}
			continue
		}

		if st.scheduled[alt.Package] {
			// Already pending elsewhere in the worklist; its own range
			// constraint set already carries this requirement once it is
			// reached, so nothing new needs scheduling here.
			if result := solve(idx+1, st); result != nil {
				return result
			}
			continue
		}

		nextRanges := cloneRanges(st.ranges)
		nextRanges[alt.Package] = append(nextRanges[alt.Package], r)
		nextScheduled := cloneScheduled(st.scheduled)
		nextScheduled[alt.Package] = true
		nextWorklist := append([]worklistItem(nil), st.worklist...)
		nextWorklist = append(nextWorklist, worklistItem{pkg: alt.Package})

		result := solve(idx+1, &solverState{
			reg:       st.reg,
			assigned:  st.assigned,
			ranges:    nextRanges,
			worklist:  nextWorklist,
			scheduled: nextScheduled,
		})
		if result != nil {
			return result
		}
	}
	return nil
}

// solvePackage assigns pkg a candidate version, newest first, propagating
// whatever new plain requirements and any_of groups that choice adds, and
// backtracks to the next candidate the moment one is proven inconsistent.
func solvePackage(idx int, pkg string, st *solverState) map[string]version {
	if _, already := st.assigned[pkg]; already {
		return solve(idx+1, st)
	}

	for _, v := range candidateVersions(st.reg, pkg, st.ranges[pkg]) {
		if conflictsWithAssigned(st.reg, pkg, v, st.assigned) {
			continue
		}

		nextAssigned := cloneAssigned(st.assigned)
		nextAssigned[pkg] = v
		nextRanges := cloneRanges(st.ranges)
		nextScheduled := cloneScheduled(st.scheduled)

		idxEntry := st.reg.byPkg[pkg][v.String()]
		failed := false
		var newPkgNames []string
		var newAnyOfItems []worklistItem
		for _, req := range idxEntry.Requires {
			if req.AnyOf != nil {
				newAnyOfItems = append(newAnyOfItems, worklistItem{anyOf: req.AnyOf})
				continue
			}
			r, err := parseRange(req.Range)
			if err != nil {
				failed = true
				break
			}
			if av, ok := nextAssigned[req.Package]; ok {
				if !r.matches(av) {
					failed = true
					break
				}
				continue
			}
			nextRanges[req.Package] = append(nextRanges[req.Package], r)
			if !nextScheduled[req.Package] {
				nextScheduled[req.Package] = true
				newPkgNames = append(newPkgNames, req.Package)
			}
		}
		if failed {
			continue
		}

		// Rebuild the pending package tail exactly as before: merge every
		// still-pending package name (old and new) and re-sort, so a graph
		// with no any_of groups explores in the same canonical order as
		// prior to this function's split. Pending any_of groups keep their
		// relative order and simply gain any newly discovered ones at the
		// end.
		var pkgTail []string
		var anyOfTail []worklistItem
		for _, it := range st.worklist[idx+1:] {
			if it.anyOf != nil {
				anyOfTail = append(anyOfTail, it)
			} else {
				pkgTail = append(pkgTail, it.pkg)
			}
		}
		pkgTail = append(pkgTail, newPkgNames...)
		sort.Strings(pkgTail)

		nextWorklist := append([]worklistItem(nil), st.worklist[:idx+1]...)
		for _, name := range pkgTail {
			nextWorklist = append(nextWorklist, worklistItem{pkg: name})
		}
		nextWorklist = append(nextWorklist, anyOfTail...)
		nextWorklist = append(nextWorklist, newAnyOfItems...)

		result := solve(idx+1, &solverState{
			reg:       st.reg,
			assigned:  nextAssigned,
			ranges:    nextRanges,
			worklist:  nextWorklist,
			scheduled: nextScheduled,
		})
		if result != nil {
			return result
		}
	}
	return nil
}

func resolveAll(reg *registry, rootReqs []plainReq) (map[string]version, error) {
	ranges := map[string][]verRange{}
	scheduled := map[string]bool{}
	var names []string
	for _, req := range rootReqs {
		r, err := parseRange(req.Range)
		if err != nil {
			return nil, err
		}
		ranges[req.Package] = append(ranges[req.Package], r)
		if !scheduled[req.Package] {
			scheduled[req.Package] = true
			names = append(names, req.Package)
		}
	}
	sort.Strings(names)
	worklist := make([]worklistItem, len(names))
	for i, name := range names {
		worklist[i] = worklistItem{pkg: name}
	}

	st := &solverState{
		reg:       reg,
		assigned:  map[string]version{},
		ranges:    ranges,
		worklist:  worklist,
		scheduled: scheduled,
	}
	result := solve(0, st)
	if result == nil {
		return nil, fmt.Errorf("no assignment satisfies the manifest")
	}
	return result, nil
}

// ---------- main ----------

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: resolver <registry-dir> <manifest-path> <lock-out-path>")
		os.Exit(1)
	}
	regRoot := os.Args[1]
	manifestPath := os.Args[2]
	lockPath := os.Args[3]

	reg, err := loadRegistry(regRoot)
	if err != nil {
		fmt.Fprintln(os.Stderr, "load registry:", err)
		os.Exit(1)
	}
	rootReqs, err := loadManifestRequires(manifestPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "load manifest:", err)
		os.Exit(1)
	}
	solution, err := resolveAll(reg, rootReqs)
	if err != nil {
		fmt.Fprintln(os.Stderr, "resolve:", err)
		os.Exit(1)
	}

	lock := make(map[string]string, len(solution))
	names := make([]string, 0, len(solution))
	for pkg := range solution {
		names = append(names, pkg)
	}
	sort.Strings(names)
	for _, pkg := range names {
		lock[pkg] = solution[pkg].String()
	}

	if err := os.MkdirAll(filepath.Dir(lockPath), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, "mkdir out:", err)
		os.Exit(1)
	}
	// R10: keys in ascending lexicographic order. names is already sorted
	// above; build the JSON text by hand instead of json.Marshal on a Go
	// map (Go's json package re-sorts map keys itself, so this happens to
	// agree, but writing it explicitly keeps the ordering guarantee
	// independent of that implementation detail).
	var b strings.Builder
	b.WriteString("{\n")
	for i, pkg := range names {
		fmt.Fprintf(&b, "  %q: %q", pkg, lock[pkg])
		if i < len(names)-1 {
			b.WriteString(",")
		}
		b.WriteString("\n")
	}
	b.WriteString("}\n")
	if err := os.WriteFile(lockPath, []byte(b.String()), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, "write lock:", err)
		os.Exit(1)
	}
}
