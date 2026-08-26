package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
)

type Claim struct {
	Name     string `json:"name"`
	Strength int    `json:"strength"`
}

type Requirement struct {
	Name        string `json:"name"`
	MinStrength int    `json:"min_strength"`
}

type Request struct {
	GeneratedAt       string         `json:"generated_at"`
	RolloutID         string         `json:"rollout_id"`
	TargetRuntime     string         `json:"target_runtime"`
	AllowedTracks     []string       `json:"allowed_tracks"`
	RevokedIssuers    []string       `json:"revoked_issuers"`
	MaxFootprintKB    int            `json:"max_total_footprint_kb"`
	IssuerCaps        map[string]int `json:"issuer_caps"`
	BaselineClaims    []Claim        `json:"baseline_claims"`
	RequiredClaims    []Requirement  `json:"required_claims"`
}

type Prerequisite struct {
	Name        string `json:"name"`
	MinStrength int    `json:"min_strength"`
}

type Bundle struct {
	ID           string         `json:"id"`
	Family       string         `json:"family"`
	Version      string         `json:"version"`
	Runtime      string         `json:"runtime"`
	Track        string         `json:"track"`
	Issuer       string         `json:"issuer"`
	FootprintKB  int            `json:"footprint_kb"`
	Risk         int            `json:"risk"`
	Slot         *string        `json:"slot"`
	Claims       []Claim        `json:"claims"`
	Prereqs      []Prerequisite `json:"prerequisites"`
	Excludes     []string       `json:"excludes"`
}

type Catalog struct {
	Bundles []Bundle `json:"bundles"`
}

type ClaimStrength struct {
	Name     string `json:"name"`
	Strength int    `json:"strength"`
}

type Summary struct {
	TotalFootprintKB int             `json:"total_footprint_kb"`
	TotalRisk        int             `json:"total_risk"`
	ClaimStrengths   []ClaimStrength `json:"claim_strengths"`
	MissingClaims    []string        `json:"missing_claims"`
}

type Output struct {
	GeneratedAt       string   `json:"generated_at"`
	Status            string   `json:"status"`
	SelectedBundleIDs []string `json:"selected_bundle_ids"`
	Summary           Summary  `json:"summary"`
}

type BundleGroup struct {
	Key     string
	Bundles []Bundle
}

type SearchState struct {
	BestScore  [4]int
	HasBest    bool
	BestOrder  []string
	BestSubset []Bundle
}

func scoreBetter(left, right [4]int) bool {
	for i := 0; i < len(left); i++ {
		if left[i] == right[i] {
			continue
		}
		return left[i] > right[i]
	}
	return false
}

func readJSON(path string, target any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, target)
}

func writeJSON(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o644)
}

func isUsable(bundle Bundle, request Request) bool {
	if bundle.Runtime != request.TargetRuntime {
		return false
	}
	allowed := false
	for _, track := range request.AllowedTracks {
		if track == bundle.Track {
			allowed = true
			break
		}
	}
	if !allowed {
		return false
	}
	for _, revoked := range request.RevokedIssuers {
		if revoked == bundle.Issuer {
			return false
		}
	}
	return true
}

func groupBundles(bundles []Bundle) []BundleGroup {
	grouped := map[string][]Bundle{}
	for _, bundle := range bundles {
		key := bundle.ID
		if bundle.Slot != nil {
			key = *bundle.Slot
		}
		grouped[key] = append(grouped[key], bundle)
	}

	keys := make([]string, 0, len(grouped))
	for key := range grouped {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		left := grouped[keys[i]]
		right := grouped[keys[j]]
		leftWeight := 0
		rightWeight := 0
		for _, bundle := range left {
			leftWeight += len(bundle.Claims) + len(bundle.Prereqs) + len(bundle.Excludes)
		}
		for _, bundle := range right {
			rightWeight += len(bundle.Claims) + len(bundle.Prereqs) + len(bundle.Excludes)
		}
		if leftWeight != rightWeight {
			return leftWeight > rightWeight
		}
		if len(left) != len(right) {
			return len(left) > len(right)
		}
		return keys[i] < keys[j]
	})

	groups := make([]BundleGroup, 0, len(keys))
	for _, key := range keys {
		rows := append([]Bundle{}, grouped[key]...)
		sort.Slice(rows, func(i, j int) bool { return rows[i].ID < rows[j].ID })
		groups = append(groups, BundleGroup{Key: key, Bundles: rows})
	}
	return groups
}

func claimStrengths(selected []Bundle, baseline []Claim) map[string]int {
	strengths := map[string]int{}
	for _, row := range baseline {
		strengths[row.Name] = row.Strength
	}
	for _, bundle := range selected {
		for _, row := range bundle.Claims {
			if strengths[row.Name] < row.Strength {
				strengths[row.Name] = row.Strength
			}
		}
	}
	return strengths
}

func selectedSetValid(selected []Bundle, request Request) bool {
	families := map[string]bool{}
	slots := map[string]bool{}
	issuerCounts := map[string]int{}
	totalFootprint := 0

	for _, bundle := range selected {
		if families[bundle.Family] {
			return false
		}
		families[bundle.Family] = true

		if bundle.Slot != nil {
			if slots[*bundle.Slot] {
				return false
			}
			slots[*bundle.Slot] = true
		}

		totalFootprint += bundle.FootprintKB
		if totalFootprint > request.MaxFootprintKB {
			return false
		}

		issuerCounts[bundle.Issuer]++
		if capValue, ok := request.IssuerCaps[bundle.Issuer]; ok && issuerCounts[bundle.Issuer] > capValue {
			return false
		}
	}

	strengths := claimStrengths(selected, request.BaselineClaims)
	for _, bundle := range selected {
		for _, prereq := range bundle.Prereqs {
			if strengths[prereq.Name] < prereq.MinStrength {
				return false
			}
		}
		for _, token := range bundle.Excludes {
			for _, other := range selected {
				if other.ID == bundle.ID {
					continue
				}
				if other.Family == token {
					return false
				}
				for _, claim := range other.Claims {
					if claim.Name == token {
						return false
					}
				}
			}
		}
	}
	return true
}

func canonicalActivationOrder(selected []Bundle, baseline []Claim) []string {
	remaining := map[string]Bundle{}
	for _, bundle := range selected {
		remaining[bundle.ID] = bundle
	}
	strengths := map[string]int{}
	for _, row := range baseline {
		strengths[row.Name] = row.Strength
	}

	order := make([]string, 0, len(selected))
	for len(remaining) > 0 {
		ready := make([]string, 0)
		for bundleID, bundle := range remaining {
			ok := true
			for _, prereq := range bundle.Prereqs {
				if strengths[prereq.Name] < prereq.MinStrength {
					ok = false
					break
				}
			}
			if ok {
				ready = append(ready, bundleID)
			}
		}
		if len(ready) == 0 {
			return nil
		}
		sort.Strings(ready)
		bundle := remaining[ready[0]]
		delete(remaining, ready[0])
		order = append(order, ready[0])
		for _, claim := range bundle.Claims {
			if strengths[claim.Name] < claim.Strength {
				strengths[claim.Name] = claim.Strength
			}
		}
	}
	return order
}

func satisfiedCount(request Request, strengths map[string]int) int {
	count := 0
	for _, row := range request.RequiredClaims {
		if strengths[row.Name] >= row.MinStrength {
			count++
		}
	}
	return count
}

func conflictTokens(bundle Bundle) map[string]bool {
	tokens := map[string]bool{bundle.Family: true}
	for _, token := range bundle.Excludes {
		tokens[token] = true
	}
	for _, claim := range bundle.Claims {
		tokens[claim.Name] = true
	}
	return tokens
}

func conflictsWithSelected(bundle Bundle, selected []Bundle) bool {
	leftExcludes := map[string]bool{}
	for _, token := range bundle.Excludes {
		leftExcludes[token] = true
	}
	leftTokens := conflictTokens(bundle)

	for _, other := range selected {
		rightTokens := conflictTokens(other)
		for token := range leftExcludes {
			if rightTokens[token] {
				return true
			}
		}
		for _, token := range other.Excludes {
			if leftTokens[token] {
				return true
			}
		}
	}
	return false
}

func suffixClaimBounds(groups []BundleGroup) []map[string]int {
	suffix := make([]map[string]int, len(groups)+1)
	suffix[len(groups)] = map[string]int{}
	for index := len(groups) - 1; index >= 0; index-- {
		merged := map[string]int{}
		for key, value := range suffix[index+1] {
			merged[key] = value
		}
		local := map[string]int{}
		for _, bundle := range groups[index].Bundles {
			for _, row := range bundle.Claims {
				if local[row.Name] < row.Strength {
					local[row.Name] = row.Strength
				}
			}
		}
		for key, value := range local {
			if merged[key] < value {
				merged[key] = value
			}
		}
		suffix[index] = merged
	}
	return suffix
}

func upperBoundSatisfied(request Request, strengths map[string]int, future map[string]int) int {
	count := 0
	for _, row := range request.RequiredClaims {
		current := strengths[row.Name]
		if future[row.Name] > current {
			current = future[row.Name]
		}
		if current >= row.MinStrength {
			count++
		}
	}
	return count
}

func selectedPrereqsStillPossible(selected []Bundle, strengths map[string]int, future map[string]int) bool {
	for _, bundle := range selected {
		for _, prereq := range bundle.Prereqs {
			current := strengths[prereq.Name]
			if future[prereq.Name] > current {
				current = future[prereq.Name]
			}
			if current < prereq.MinStrength {
				return false
			}
		}
	}
	return true
}

func lexicographicallyLess(left, right []string) bool {
	for i := 0; i < len(left) && i < len(right); i++ {
		if left[i] == right[i] {
			continue
		}
		return left[i] < right[i]
	}
	return len(left) < len(right)
}

func solve(request Request, catalog Catalog) Output {
	usable := make([]Bundle, 0, len(catalog.Bundles))
	for _, bundle := range catalog.Bundles {
		if isUsable(bundle, request) {
			usable = append(usable, bundle)
		}
	}
	groups := groupBundles(usable)
	suffixBounds := suffixClaimBounds(groups)

	state := SearchState{}

	var search func(index int, selected []Bundle, usedFamilies map[string]bool, issuerCounts map[string]int, totalFootprint int)
	search = func(index int, selected []Bundle, usedFamilies map[string]bool, issuerCounts map[string]int, totalFootprint int) {
		if totalFootprint > request.MaxFootprintKB {
			return
		}
		for issuer, count := range issuerCounts {
			if capValue, ok := request.IssuerCaps[issuer]; ok && count > capValue {
				return
			}
		}

		strengths := claimStrengths(selected, request.BaselineClaims)
		if !selectedPrereqsStillPossible(selected, strengths, suffixBounds[index]) {
			return
		}
		if state.HasBest && upperBoundSatisfied(request, strengths, suffixBounds[index]) < state.BestScore[0] {
			return
		}

		if index == len(groups) {
			if !selectedSetValid(selected, request) {
				return
			}
			order := canonicalActivationOrder(selected, request.BaselineClaims)
			if order == nil {
				return
			}
			score := [4]int{
				satisfiedCount(request, strengths),
				-sumRisk(selected),
				-totalFootprint,
				-len(selected),
			}
			if !state.HasBest || scoreBetter(score, state.BestScore) || (score == state.BestScore && lexicographicallyLess(order, state.BestOrder)) {
				state.HasBest = true
				state.BestScore = score
				state.BestOrder = append([]string{}, order...)
				state.BestSubset = append([]Bundle{}, selected...)
			}
			return
		}

		search(index+1, selected, usedFamilies, issuerCounts, totalFootprint)

		for _, bundle := range groups[index].Bundles {
			if usedFamilies[bundle.Family] {
				continue
			}
			if conflictsWithSelected(bundle, selected) {
				continue
			}
			if capValue, ok := request.IssuerCaps[bundle.Issuer]; ok && issuerCounts[bundle.Issuer] >= capValue {
				continue
			}

			selected = append(selected, bundle)
			usedFamilies[bundle.Family] = true
			issuerCounts[bundle.Issuer]++
			search(index+1, selected, usedFamilies, issuerCounts, totalFootprint+bundle.FootprintKB)
			issuerCounts[bundle.Issuer]--
			if issuerCounts[bundle.Issuer] == 0 {
				delete(issuerCounts, bundle.Issuer)
			}
			delete(usedFamilies, bundle.Family)
			selected = selected[:len(selected)-1]
		}
	}

	search(0, []Bundle{}, map[string]bool{}, map[string]int{}, 0)

	if !state.HasBest {
		state.HasBest = true
		state.BestOrder = []string{}
		state.BestSubset = []Bundle{}
		state.BestScore = [4]int{0, 0, 0, 0}
	}

	finalStrengths := claimStrengths(state.BestSubset, request.BaselineClaims)
	claimRows := make([]ClaimStrength, 0, len(request.RequiredClaims))
	missing := make([]string, 0)
	for _, row := range request.RequiredClaims {
		strength := finalStrengths[row.Name]
		claimRows = append(claimRows, ClaimStrength{Name: row.Name, Strength: strength})
		if strength < row.MinStrength {
			missing = append(missing, row.Name)
		}
	}

	status := "ready"
	if len(missing) > 0 {
		status = "gap"
	}
	return Output{
		GeneratedAt:       request.GeneratedAt,
		Status:            status,
		SelectedBundleIDs: state.BestOrder,
		Summary: Summary{
			TotalFootprintKB: sumFootprint(state.BestSubset),
			TotalRisk:        sumRisk(state.BestSubset),
			ClaimStrengths:   claimRows,
			MissingClaims:    missing,
		},
	}
}

func sumRisk(selected []Bundle) int {
	total := 0
	for _, bundle := range selected {
		total += bundle.Risk
	}
	return total
}

func sumFootprint(selected []Bundle) int {
	total := 0
	for _, bundle := range selected {
		total += bundle.FootprintKB
	}
	return total
}

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: keyring_cutover_gate <request.json> <catalog.json> <cutover_plan.json>")
		os.Exit(1)
	}

	var request Request
	var catalog Catalog
	if err := readJSON(os.Args[1], &request); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := readJSON(os.Args[2], &catalog); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	output := solve(request, catalog)
	if err := writeJSON(os.Args[3], output); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
