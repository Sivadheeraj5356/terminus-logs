package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type Trust struct {
	Rank      int
	Risk      int
	Threshold int
	Keys      map[string]bool
}

type Hold struct {
	Cache  string
	Store  string
	Until  string
	Reason string
}

type Object struct {
	Store        string
	System       string
	Mode         string
	OutputHash   string
	BuildCost    int
	BuildAllowed bool
	Risk         int
	Refs         []string
}

type Nar struct {
	Store    string
	Cache    string
	NarHash  string
	NarSize  int
	Sigs     map[string]bool
	Refs     []string
	Deriver  string
	Filename string
}

type Case struct {
	System     string
	Now        string
	LimitNar   int
	LimitBuild int
	LimitRisk  int
	Trust      map[string]Trust
	Holds      []Hold
	Roots      []string
	Local      map[string]bool
	Objects    map[string]Object
	Nars       []Nar
}

type Cand struct {
	Store     string
	Kind      string
	Source    string
	Valid     bool
	Reason    string
	Risk      int
	NarSize   int
	BuildCost int
	Cache     *string
	NarHash   *string
	SigCount  int
	Refs      []string
	Mode      string
}

type ClosureOut struct {
	Status  string      `json:"status"`
	Roots   []string    `json:"roots"`
	Actions []ActionOut `json:"actions"`
	Summary SummaryOut  `json:"summary"`
}

type ActionOut struct {
	Store      string   `json:"store"`
	Action     string   `json:"action"`
	Cache      *string  `json:"cache"`
	NarHash    *string  `json:"nar_hash"`
	NarSize    int      `json:"nar_size"`
	BuildCost  int      `json:"build_cost"`
	Risk       int      `json:"risk"`
	References []string `json:"references"`
}

type SummaryOut struct {
	Local          int     `json:"local"`
	Substituted    int     `json:"substituted"`
	Built          int     `json:"built"`
	TotalNarSize   int     `json:"total_nar_size"`
	TotalBuildCost int     `json:"total_build_cost"`
	TotalRisk      int     `json:"total_risk"`
	Reason         *string `json:"reason"`
}

type ProofOut struct {
	Closure    []string       `json:"closure"`
	Candidates []CandidateOut `json:"candidates"`
	Selected   []string       `json:"selected"`
	Seal       string         `json:"seal"`
}

type CandidateOut struct {
	Store     string `json:"store"`
	Source    string `json:"source"`
	Valid     bool   `json:"valid"`
	Reason    string `json:"reason"`
	Risk      int    `json:"risk"`
	NarSize   int    `json:"nar_size"`
	BuildCost int    `json:"build_cost"`
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: closure-plan CASE_ROOT OUTDIR")
		os.Exit(2)
	}
	if err := run(os.Args[1], os.Args[2]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(root, outDir string) error {
	closure, tsv, proof, err := solve(root)
	if err != nil {
		return err
	}
	closureBytes, err := json.Marshal(closure)
	if err != nil {
		return err
	}
	closureRaw := string(closureBytes) + "\n"
	seal := sha256.Sum256([]byte(closureRaw + "\n" + tsv))
	proof.Seal = hex.EncodeToString(seal[:])
	proofBytes, err := json.Marshal(proof)
	if err != nil {
		return err
	}
	if err := os.RemoveAll(outDir); err != nil {
		return err
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "closure.json"), []byte(closureRaw), 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "actions.tsv"), []byte(tsv), 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outDir, "proof.json"), append(proofBytes, '\n'), 0o644)
}

func solve(root string) (ClosureOut, string, ProofOut, error) {
	c, err := readCase(root)
	if err != nil {
		return ClosureOut{}, "", ProofOut{}, err
	}
	required, ok := closure(c)
	if !ok {
		return unsat(nil, nil), unsatTSV(), ProofOut{Closure: []string{}, Candidates: []CandidateOut{}, Selected: []string{}}, nil
	}
	all := make(map[string][]Cand)
	validLists := make([][]Cand, 0, len(required))
	hasEmpty := false
	for _, store := range required {
		cands := candidatesFor(c, store)
		all[store] = cands
		var valid []Cand
		for _, cand := range cands {
			if cand.Valid {
				valid = append(valid, cand)
			}
		}
		if len(valid) == 0 {
			hasEmpty = true
		}
		validLists = append(validLists, valid)
	}
	if hasEmpty {
		return unsat(required, all), unsatTSV(), ProofOut{Closure: []string{}, Candidates: candidateRows(required, all), Selected: []string{}}, nil
	}

	var best []Cand
	haveBest := false
	var walk func(int, []Cand)
	walk = func(index int, current []Cand) {
		if index == len(validLists) {
			if !withinBudgets(current, c) {
				return
			}
			if !haveBest || better(current, best, c) {
				best = append([]Cand(nil), current...)
				haveBest = true
			}
			return
		}
		for _, cand := range validLists[index] {
			walk(index+1, append(current, cand))
		}
	}
	walk(0, nil)
	if !haveBest {
		return unsat(required, all), unsatTSV(), ProofOut{Closure: []string{}, Candidates: candidateRows(required, all), Selected: []string{}}, nil
	}
	closureOut, tsv, proof := okOutputs(c, required, all, best)
	return closureOut, tsv, proof, nil
}

func okOutputs(c Case, required []string, all map[string][]Cand, best []Cand) (ClosureOut, string, ProofOut) {
	byStore := make(map[string]Cand)
	for _, cand := range best {
		byStore[cand.Store] = cand
	}
	stores := make([]string, 0, len(byStore))
	for store := range byStore {
		stores = append(stores, store)
	}
	sort.Strings(stores)
	var actions []ActionOut
	for _, store := range stores {
		cand := byStore[store]
		actions = append(actions, ActionOut{
			Store:      store,
			Action:     cand.Kind,
			Cache:      cand.Cache,
			NarHash:    cand.NarHash,
			NarSize:    cand.NarSize,
			BuildCost:  cand.BuildCost,
			Risk:       cand.Risk,
			References: cloneList(cand.Refs),
		})
	}
	summary := SummaryOut{Reason: nil}
	for _, cand := range best {
		switch cand.Kind {
		case "local":
			summary.Local++
		case "substitute":
			summary.Substituted++
			summary.TotalNarSize += cand.NarSize
		case "build":
			summary.Built++
			summary.TotalBuildCost += cand.BuildCost
		}
		summary.TotalRisk += cand.Risk
	}
	roots := append([]string(nil), c.Roots...)
	sort.Strings(roots)
	closure := ClosureOut{Status: "ok", Roots: roots, Actions: actions, Summary: summary}
	tsv := "store\taction\tcache\tnar_size\tbuild_cost\trisk\tdetail\n"
	for _, store := range stores {
		cand := byStore[store]
		cache := "-"
		if cand.Cache != nil {
			cache = *cand.Cache
		}
		detail := ""
		switch cand.Kind {
		case "local":
			detail = "present"
		case "build":
			detail = "mode=" + cand.Mode
		case "substitute":
			detail = fmt.Sprintf("sig=%d;refs=%d", cand.SigCount, len(cand.Refs))
		}
		tsv += fmt.Sprintf("%s\t%s\t%s\t%d\t%d\t%d\t%s\n", store, cand.Kind, cache, cand.NarSize, cand.BuildCost, cand.Risk, detail)
	}
	proof := ProofOut{Closure: required, Candidates: candidateRows(required, all), Selected: signatures(best)}
	return closure, tsv, proof
}

func unsat(_ []string, _ map[string][]Cand) ClosureOut {
	reason := "no_plan"
	return ClosureOut{
		Status:  "unsat",
		Roots:   []string{},
		Actions: []ActionOut{},
		Summary: SummaryOut{Reason: &reason},
	}
}

func unsatTSV() string {
	return "store\taction\tcache\tnar_size\tbuild_cost\trisk\tdetail\nNONE\tunsat\t-\t0\t0\t0\tno_plan\n"
}

func readCase(root string) (Case, error) {
	c := Case{Trust: map[string]Trust{}, Local: map[string]bool{}, Objects: map[string]Object{}}
	if err := readPolicy(filepath.Join(root, "policy.txt"), &c); err != nil {
		return c, err
	}
	if err := readRoots(filepath.Join(root, "roots.txt"), &c); err != nil {
		return c, err
	}
	if err := readLocal(filepath.Join(root, "local.txt"), &c); err != nil {
		return c, err
	}
	if err := readObjects(filepath.Join(root, "objects.txt"), &c); err != nil {
		return c, err
	}
	if err := readNars(filepath.Join(root, "narinfo"), &c); err != nil {
		return c, err
	}
	return c, nil
}

func lines(path string) ([][]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	var rows [][]string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		rows = append(rows, strings.Fields(line))
	}
	return rows, scanner.Err()
}

func readPolicy(path string, c *Case) error {
	rows, err := lines(path)
	if err != nil {
		return err
	}
	for _, parts := range rows {
		switch parts[0] {
		case "SYSTEM":
			c.System = parts[1]
		case "NOW":
			c.Now = parts[1]
		case "LIMIT_NAR":
			c.LimitNar = atoi(parts[1])
		case "LIMIT_BUILD":
			c.LimitBuild = atoi(parts[1])
		case "LIMIT_RISK":
			c.LimitRisk = atoi(parts[1])
		case "TRUST":
			c.Trust[parts[1]] = Trust{Rank: atoi(parts[2]), Risk: atoi(parts[3]), Threshold: atoi(parts[4]), Keys: setOf(parts[5])}
		case "HOLD":
			c.Holds = append(c.Holds, Hold{Cache: parts[1], Store: parts[2], Until: parts[3], Reason: parts[4]})
		default:
			return fmt.Errorf("unknown policy tag %s", parts[0])
		}
	}
	return nil
}

func readRoots(path string, c *Case) error {
	rows, err := lines(path)
	if err != nil {
		return err
	}
	for _, parts := range rows {
		if parts[0] != "ROOT" {
			return fmt.Errorf("unknown roots tag %s", parts[0])
		}
		c.Roots = append(c.Roots, parts[1])
	}
	return nil
}

func readLocal(path string, c *Case) error {
	rows, err := lines(path)
	if err != nil {
		return err
	}
	for _, parts := range rows {
		if parts[0] != "LOCAL" {
			return fmt.Errorf("unknown local tag %s", parts[0])
		}
		c.Local[parts[1]] = true
	}
	return nil
}

func readObjects(path string, c *Case) error {
	rows, err := lines(path)
	if err != nil {
		return err
	}
	for _, parts := range rows {
		if parts[0] != "OBJECT" {
			return fmt.Errorf("unknown object tag %s", parts[0])
		}
		refs := listOf(parts[8])
		c.Objects[parts[1]] = Object{
			Store:        parts[1],
			System:       parts[2],
			Mode:         parts[3],
			OutputHash:   parts[4],
			BuildCost:    atoi(parts[5]),
			BuildAllowed: parts[6] == "yes",
			Risk:         atoi(parts[7]),
			Refs:         refs,
		}
	}
	return nil
}

func readNars(dir string, c *Case) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".nar") {
			continue
		}
		rows, err := lines(filepath.Join(dir, entry.Name()))
		if err != nil {
			return err
		}
		fields := map[string]string{}
		for _, parts := range rows {
			fields[parts[0]] = parts[1]
		}
		c.Nars = append(c.Nars, Nar{
			Store:    fields["STORE"],
			Cache:    fields["CACHE"],
			NarHash:  fields["NAR_HASH"],
			NarSize:  atoi(fields["NAR_SIZE"]),
			Sigs:     setOf(fields["SIGS"]),
			Refs:     listOf(fields["REFERENCES"]),
			Deriver:  fields["DERIVER"],
			Filename: entry.Name(),
		})
	}
	return nil
}

func closure(c Case) ([]string, bool) {
	seen := map[string]bool{}
	stack := append([]string(nil), c.Roots...)
	for len(stack) > 0 {
		store := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		if seen[store] {
			continue
		}
		obj, ok := c.Objects[store]
		if !ok {
			return nil, false
		}
		seen[store] = true
		stack = append(stack, obj.Refs...)
	}
	var out []string
	for store := range seen {
		out = append(out, store)
	}
	sort.Strings(out)
	return out, true
}

func candidatesFor(c Case, store string) []Cand {
	obj := c.Objects[store]
	var out []Cand
	if c.Local[store] {
		valid := obj.System == c.System
		reason := "ok"
		if !valid {
			reason = "system_mismatch"
		}
		out = append(out, Cand{Store: store, Kind: "local", Source: "local", Valid: valid, Reason: reason, Refs: obj.Refs, Mode: obj.Mode})
	}
	buildValid := obj.System == c.System && obj.BuildAllowed && (obj.Mode == "input" || obj.OutputHash != "-")
	buildReason := "ok"
	if obj.System != c.System {
		buildReason = "system_mismatch"
	} else if !buildValid {
		buildReason = "build_forbidden"
	}
	out = append(out, Cand{Store: store, Kind: "build", Source: "build", Valid: buildValid, Reason: buildReason, Risk: obj.Risk, BuildCost: obj.BuildCost, Refs: obj.Refs, Mode: obj.Mode})
	var nars []Nar
	for _, nar := range c.Nars {
		if nar.Store == store {
			nars = append(nars, nar)
		}
	}
	sort.Slice(nars, func(i, j int) bool {
		a := []string{nars[i].Cache, nars[i].NarHash, nars[i].Filename}
		b := []string{nars[j].Cache, nars[j].NarHash, nars[j].Filename}
		return strings.Join(a, "\x00") < strings.Join(b, "\x00")
	})
	for _, nar := range nars {
		out = append(out, substitute(c, obj, nar))
	}
	return out
}

func substitute(c Case, obj Object, nar Nar) Cand {
	valid := true
	reason := "ok"
	trust, ok := c.Trust[nar.Cache]
	risk := obj.Risk
	sigCount := 0
	if !ok {
		valid = false
		reason = "untrusted_cache"
	} else {
		risk += trust.Risk
		for sig := range nar.Sigs {
			if trust.Keys[sig] {
				sigCount++
			}
		}
		if obj.System != c.System {
			valid = false
			reason = "system_mismatch"
		} else if hold := activeHold(c, nar.Cache, obj.Store); hold != "" {
			valid = false
			reason = "active_hold:" + hold
		} else if sigCount < trust.Threshold {
			valid = false
			reason = "bad_signature"
		} else if !sameList(nar.Refs, obj.Refs) {
			valid = false
			reason = "ref_mismatch"
		} else if (obj.Mode == "fixed" || obj.Mode == "ca") && nar.NarHash != obj.OutputHash {
			valid = false
			reason = "hash_mismatch"
		}
	}
	cache := nar.Cache
	hash := nar.NarHash
	return Cand{Store: obj.Store, Kind: "substitute", Source: nar.Cache, Valid: valid, Reason: reason, Risk: risk, NarSize: nar.NarSize, Cache: &cache, NarHash: &hash, SigCount: sigCount, Refs: obj.Refs, Mode: obj.Mode}
}

func activeHold(c Case, cache, store string) string {
	for _, hold := range c.Holds {
		if hold.Cache == cache && hold.Store == store && hold.Until >= c.Now {
			return hold.Reason
		}
	}
	return ""
}

func withinBudgets(plan []Cand, c Case) bool {
	var nar, build, risk int
	for _, cand := range plan {
		if cand.Kind == "substitute" {
			nar += cand.NarSize
		}
		if cand.Kind == "build" {
			build += cand.BuildCost
		}
		risk += cand.Risk
	}
	return nar <= c.LimitNar && build <= c.LimitBuild && risk <= c.LimitRisk
}

func better(left, right []Cand, c Case) bool {
	lkey := planKey(left, c)
	rkey := planKey(right, c)
	for i := range lkey {
		if lkey[i] != rkey[i] {
			return lkey[i] > rkey[i]
		}
	}
	ls := signatures(left)
	rs := signatures(right)
	for i := range ls {
		if ls[i] != rs[i] {
			return ls[i] < rs[i]
		}
	}
	return false
}

func planKey(plan []Cand, c Case) []int {
	var built, risk, nar, build, rank int
	for _, cand := range plan {
		switch cand.Kind {
		case "build":
			built++
			build += cand.BuildCost
		case "substitute":
			nar += cand.NarSize
			if cand.Cache != nil {
				rank += c.Trust[*cand.Cache].Rank
			}
		}
		risk += cand.Risk
	}
	return []int{-built, -risk, -nar, -build, rank}
}

func signatures(plan []Cand) []string {
	var sigs []string
	for _, cand := range plan {
		cache := "-"
		if cand.Cache != nil {
			cache = *cand.Cache
		}
		sigs = append(sigs, cand.Store+":"+cand.Kind+":"+cache)
	}
	sort.Strings(sigs)
	return sigs
}

func candidateRows(required []string, all map[string][]Cand) []CandidateOut {
	var rows []CandidateOut
	for _, store := range required {
		for _, cand := range all[store] {
			rows = append(rows, CandidateOut{Store: cand.Store, Source: cand.Source, Valid: cand.Valid, Reason: cand.Reason, Risk: cand.Risk, NarSize: cand.NarSize, BuildCost: cand.BuildCost})
		}
	}
	return rows
}

func atoi(value string) int {
	n, err := strconv.Atoi(value)
	if err != nil {
		panic(err)
	}
	return n
}

func setOf(value string) map[string]bool {
	out := map[string]bool{}
	if value == "-" {
		return out
	}
	for _, part := range strings.Split(value, ",") {
		if part != "" {
			out[part] = true
		}
	}
	return out
}

func listOf(value string) []string {
	if value == "-" {
		return []string{}
	}
	out := strings.Split(value, ",")
	sort.Strings(out)
	return out
}

func cloneList(values []string) []string {
	out := make([]string, len(values))
	copy(out, values)
	return out
}

func sameList(left, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for i := range left {
		if left[i] != right[i] {
			return false
		}
	}
	return true
}
