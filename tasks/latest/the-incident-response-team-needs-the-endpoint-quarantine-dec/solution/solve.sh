#!/bin/bash
set -euo pipefail

cat > /app/main.go <<'GO'
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"time"
)

type Policy struct {
	EvaluationTime            string         `json:"evaluation_time"`
	RequiredFamilies          []string       `json:"required_families"`
	FamilyScores              map[string]int `json:"family_scores"`
	FamilyMinConfidence       map[string]int `json:"family_min_confidence"`
	Threshold                 int            `json:"threshold"`
	ReviewBudget              int            `json:"review_budget"`
	OutageBudget              int            `json:"outage_budget"`
	RuleSlotBudget            int            `json:"rule_slot_budget"`
	MinDistinctOwners         int            `json:"min_distinct_owners"`
	DenyTagPrefixes           []string       `json:"deny_tag_prefixes"`
	AllowedOwners             []string       `json:"allowed_owners"`
	OwnerReviewCaps           map[string]int `json:"owner_review_caps"`
	MaxActionsPerOwner        int            `json:"max_actions_per_owner"`
	ZoneBlastRadiusBudget     map[string]int `json:"zone_blast_radius_budget"`
	EscalationOutageThreshold int            `json:"escalation_outage_threshold"`
	TieMode                   string         `json:"tie_mode"`
}

type Asset struct {
	AssetID     string   `json:"asset_id"`
	Zone        string   `json:"zone"`
	Criticality int      `json:"criticality"`
	DetectedAt  string   `json:"detected_at"`
	Tags        []string `json:"tags"`
}

type Action struct {
	ActionID           string   `json:"action_id"`
	AssetID            string   `json:"asset_id"`
	ActionType         string   `json:"action_type"`
	Families           []string `json:"families"`
	Owner              string   `json:"owner"`
	ReviewMinutes      int      `json:"review_minutes"`
	OutageUnits        int      `json:"outage_units"`
	RuleSlots          int      `json:"rule_slots"`
	ValidFrom          string   `json:"valid_from"`
	ExpiresAt          *string  `json:"expires_at"`
	AllowedZones       []string `json:"allowed_zones"`
	BlockedTagPrefixes []string `json:"blocked_tag_prefixes"`
	ConflictsWith      []string `json:"conflicts_with"`
	FamilyConfidence   map[string]int `json:"family_confidence"`
	RequiresAny        [][]string `json:"requires_any"`
	RequiresAllActionTypes []string `json:"requires_all_action_types"`
	BlastRadius        int      `json:"blast_radius"`
}

type Bundle struct {
	Policy  Policy   `json:"policy"`
	Assets  []Asset  `json:"assets"`
	Actions []Action `json:"actions"`
}

type AssetDecision struct {
	AssetID         string   `json:"asset_id"`
	Status          string   `json:"status"`
	SelectedActions []string `json:"selected_actions"`
	RiskScore       int      `json:"risk_score"`
	ReviewMinutes   int      `json:"review_minutes"`
	OutageUnits     int      `json:"outage_units"`
	RuleSlots       int      `json:"rule_slots"`
	SelectedOwners  []string `json:"selected_owners"`
	Reasons         []string `json:"reasons"`
}

type Decision struct {
	Status          string          `json:"status"`
	Winner          *string         `json:"winner"`
	SelectedActions []string        `json:"selected_actions"`
	RiskScore       int             `json:"risk_score"`
	ReviewMinutes   int             `json:"review_minutes"`
	OutageUnits     int             `json:"outage_units"`
	RuleSlots       int             `json:"rule_slots"`
	SelectedOwners  []string        `json:"selected_owners"`
	Assets          []AssetDecision `json:"assets"`
}

type Summary struct {
	SelectedActions []string
	RiskScore       int
	ReviewMinutes   int
	OutageUnits     int
	RuleSlots       int
	SelectedOwners  []string
}

func mustTime(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}

func startsWith(s, prefix string) bool {
	return len(s) >= len(prefix) && s[:len(prefix)] == prefix
}

func anyPrefix(values, prefixes []string) bool {
	for _, v := range values {
		for _, p := range prefixes {
			if startsWith(v, p) {
				return true
			}
		}
	}
	return false
}

func contains(xs []string, x string) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}

func usable(a Action, asset Asset, p Policy) bool {
	if a.AssetID != asset.AssetID {
		return false
	}
	now := mustTime(p.EvaluationTime)
	if mustTime(a.ValidFrom).After(now) {
		return false
	}
	if a.ExpiresAt != nil && !now.Before(mustTime(*a.ExpiresAt)) {
		return false
	}
	if len(a.AllowedZones) > 0 && !contains(a.AllowedZones, asset.Zone) {
		return false
	}
	if anyPrefix(asset.Tags, a.BlockedTagPrefixes) {
		return false
	}
	for _, family := range a.Families {
		if _, ok := p.FamilyScores[family]; !ok {
			return false
		}
	}
	for family := range a.FamilyConfidence {
		if _, ok := p.FamilyScores[family]; !ok {
			return false
		}
	}
	return contains(p.AllowedOwners, a.Owner)
}

func summarize(plan []Action, p Policy) Summary {
	confidence := map[string]int{}
	owners := map[string]bool{}
	ids := []string{}
	s := Summary{SelectedActions: []string{}, SelectedOwners: []string{}}
	for _, a := range plan {
		ids = append(ids, a.ActionID)
		owners[a.Owner] = true
		s.ReviewMinutes += a.ReviewMinutes
		s.OutageUnits += a.OutageUnits
		s.RuleSlots += a.RuleSlots
		for _, family := range a.Families {
			amount, ok := a.FamilyConfidence[family]
			if !ok {
				amount = 100
			}
			confidence[family] += amount
		}
		for family, amount := range a.FamilyConfidence {
			if !contains(a.Families, family) {
				confidence[family] += amount
			}
		}
	}
	for family, amount := range confidence {
		min := 1
		if p.FamilyMinConfidence != nil {
			if v, ok := p.FamilyMinConfidence[family]; ok {
				min = v
			}
		}
		if amount >= min {
			s.RiskScore += p.FamilyScores[family]
		}
	}
	for owner := range owners {
		s.SelectedOwners = append(s.SelectedOwners, owner)
	}
	sort.Strings(ids)
	sort.Strings(s.SelectedOwners)
	s.SelectedActions = ids
	return s
}

func lexLess(a, b []string) bool {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return len(a) < len(b)
}

func betterPlan(left []Action, right []Action, p Policy) bool {
	if right == nil {
		return true
	}
	a := summarize(left, p)
	b := summarize(right, p)
	type cmp struct {
		l, r   int
		higher bool
	}
	var checks []cmp
	if p.TieMode == "risk_then_cost" {
		checks = []cmp{{a.RiskScore, b.RiskScore, true}, {a.OutageUnits, b.OutageUnits, false}, {a.ReviewMinutes, b.ReviewMinutes, false}, {a.RuleSlots, b.RuleSlots, false}, {len(a.SelectedActions), len(b.SelectedActions), false}}
	} else {
		checks = []cmp{{a.OutageUnits, b.OutageUnits, false}, {a.ReviewMinutes, b.ReviewMinutes, false}, {a.RuleSlots, b.RuleSlots, false}, {a.RiskScore, b.RiskScore, true}, {len(a.SelectedActions), len(b.SelectedActions), false}}
	}
	for _, c := range checks {
		if c.l != c.r {
			if c.higher {
				return c.l > c.r
			}
			return c.l < c.r
		}
	}
	return lexLess(a.SelectedActions, b.SelectedActions)
}

func actionConfidence(a Action) map[string]int {
	out := map[string]int{}
	for _, family := range a.Families {
		amount, ok := a.FamilyConfidence[family]
		if !ok {
			amount = 100
		}
		out[family] += amount
	}
	for family, amount := range a.FamilyConfidence {
		if !contains(a.Families, family) {
			out[family] += amount
		}
	}
	return out
}

func riskFromConfidence(confidence map[string]int, p Policy) int {
	risk := 0
	for family, amount := range confidence {
		min := 1
		if p.FamilyMinConfidence != nil {
			if v, ok := p.FamilyMinConfidence[family]; ok {
				min = v
			}
		}
		if amount >= min {
			risk += p.FamilyScores[family]
		}
	}
	return risk
}

func requiredFamiliesReachable(confidence map[string]int, p Policy) bool {
	for _, family := range p.RequiredFamilies {
		min := 1
		if p.FamilyMinConfidence != nil {
			if v, ok := p.FamilyMinConfidence[family]; ok {
				min = v
			}
		}
		if confidence[family] < min {
			return false
		}
	}
	return true
}

func validPlan(plan []Action, p Policy, asset Asset) bool {
	if len(plan) == 0 && (p.Threshold > 0 || len(p.RequiredFamilies) > 0) {
		return false
	}
	types := map[string]bool{}
	ids := map[string]bool{}
	confidence := map[string]int{}
	owners := map[string]bool{}
	ownerReview := map[string]int{}
	ownerCount := map[string]int{}
	blastRadius := 0
	for _, a := range plan {
		ids[a.ActionID] = true
	}
	s := summarize(plan, p)
	for _, a := range plan {
		if types[a.ActionType] {
			return false
		}
		types[a.ActionType] = true
		for _, other := range a.ConflictsWith {
			if ids[other] {
				return false
			}
		}
		for _, group := range a.RequiresAny {
			if len(group) == 0 {
				return false
			}
			found := false
			for _, id := range group {
				if ids[id] {
					found = true
				}
			}
			if !found {
				return false
			}
		}
		for _, requiredType := range a.RequiresAllActionTypes {
			found := false
			for _, other := range plan {
				if other.ActionType == requiredType {
					found = true
					break
				}
			}
			if !found {
				return false
			}
		}
		owners[a.Owner] = true
		ownerReview[a.Owner] += a.ReviewMinutes
		ownerCount[a.Owner]++
		blastRadius += a.BlastRadius
		for _, family := range a.Families {
			amount, ok := a.FamilyConfidence[family]
			if !ok {
				amount = 100
			}
			confidence[family] += amount
		}
		for family, amount := range a.FamilyConfidence {
			if !contains(a.Families, family) {
				confidence[family] += amount
			}
		}
	}
	covered := map[string]bool{}
	for family, amount := range confidence {
		min := 1
		if p.FamilyMinConfidence != nil {
			if v, ok := p.FamilyMinConfidence[family]; ok {
				min = v
			}
		}
		if amount >= min {
			covered[family] = true
		}
	}
	for _, family := range p.RequiredFamilies {
		if !covered[family] {
			return false
		}
	}
	if s.RiskScore < p.Threshold || s.ReviewMinutes > p.ReviewBudget || s.OutageUnits > p.OutageBudget || s.RuleSlots > p.RuleSlotBudget {
		return false
	}
	if len(owners) < p.MinDistinctOwners {
		return false
	}
	for owner, cap := range p.OwnerReviewCaps {
		if ownerReview[owner] > cap {
			return false
		}
	}
	if p.MaxActionsPerOwner > 0 {
		for _, count := range ownerCount {
			if count > p.MaxActionsPerOwner {
				return false
			}
		}
	}
	if p.ZoneBlastRadiusBudget != nil {
		if cap, ok := p.ZoneBlastRadiusBudget[asset.Zone]; ok && blastRadius > cap {
			return false
		}
	}
	if s.OutageUnits > p.EscalationOutageThreshold && !types["management_approval"] {
		return false
	}
	return true
}

func canonicalPlan(asset Asset, b Bundle) []Action {
	usableActions := []Action{}
	for _, action := range b.Actions {
		if usable(action, asset, b.Policy) {
			usableActions = append(usableActions, action)
		}
	}
	byType := map[string][]Action{}
	typeNames := []string{}
	for _, action := range usableActions {
		if _, ok := byType[action.ActionType]; !ok {
			typeNames = append(typeNames, action.ActionType)
		}
		byType[action.ActionType] = append(byType[action.ActionType], action)
	}
	for _, typ := range typeNames {
		actions := byType[typ]
		sort.Slice(actions, func(i, j int) bool {
			leftRisk := riskFromConfidence(actionConfidence(actions[i]), b.Policy)
			rightRisk := riskFromConfidence(actionConfidence(actions[j]), b.Policy)
			if leftRisk != rightRisk {
				return leftRisk > rightRisk
			}
			if actions[i].OutageUnits != actions[j].OutageUnits {
				return actions[i].OutageUnits < actions[j].OutageUnits
			}
			if actions[i].ReviewMinutes != actions[j].ReviewMinutes {
				return actions[i].ReviewMinutes < actions[j].ReviewMinutes
			}
			if actions[i].RuleSlots != actions[j].RuleSlots {
				return actions[i].RuleSlots < actions[j].RuleSlots
			}
			return actions[i].ActionID < actions[j].ActionID
		})
		byType[typ] = actions
	}
	sort.Slice(typeNames, func(i, j int) bool {
		leftActions := byType[typeNames[i]]
		rightActions := byType[typeNames[j]]
		leftRisk := 0
		rightRisk := 0
		leftCost := 1 << 30
		rightCost := 1 << 30
		for _, action := range leftActions {
			if risk := riskFromConfidence(actionConfidence(action), b.Policy); risk > leftRisk {
				leftRisk = risk
			}
			if cost := action.OutageUnits + action.ReviewMinutes + action.RuleSlots; cost < leftCost {
				leftCost = cost
			}
		}
		for _, action := range rightActions {
			if risk := riskFromConfidence(actionConfidence(action), b.Policy); risk > rightRisk {
				rightRisk = risk
			}
			if cost := action.OutageUnits + action.ReviewMinutes + action.RuleSlots; cost < rightCost {
				rightCost = cost
			}
		}
		if leftRisk != rightRisk {
			return leftRisk > rightRisk
		}
		if leftCost != rightCost {
			return leftCost < rightCost
		}
		return typeNames[i] < typeNames[j]
	})

	suffixConfidence := make([]map[string]int, len(typeNames)+1)
	suffixOwners := make([]map[string]bool, len(typeNames)+1)
	suffixConfidence[len(typeNames)] = map[string]int{}
	suffixOwners[len(typeNames)] = map[string]bool{}
	for idx := len(typeNames) - 1; idx >= 0; idx-- {
		conf := map[string]int{}
		for family, amount := range suffixConfidence[idx+1] {
			conf[family] = amount
		}
		owners := map[string]bool{}
		for owner := range suffixOwners[idx+1] {
			owners[owner] = true
		}
		groupBest := map[string]int{}
		for _, action := range byType[typeNames[idx]] {
			for family, amount := range actionConfidence(action) {
				if amount > groupBest[family] {
					groupBest[family] = amount
				}
			}
			owners[action.Owner] = true
		}
		for family, amount := range groupBest {
			conf[family] += amount
		}
		suffixConfidence[idx] = conf
		suffixOwners[idx] = owners
	}

	var best []Action
	bestSet := false
	if b.Policy.Threshold == 0 && len(b.Policy.RequiredFamilies) == 0 {
		best = []Action{}
		bestSet = true
	}
	selected := []Action{}
	ids := map[string]bool{}
	ownerReview := map[string]int{}
	ownerCount := map[string]int{}
	confidence := map[string]int{}
	review := 0
	outage := 0
	slots := 0
	blastRadius := 0
	zoneCap, hasZoneCap := b.Policy.ZoneBlastRadiusBudget[asset.Zone]
	maxRisk := 0
	for _, points := range b.Policy.FamilyScores {
		maxRisk += points
	}

	conflictsSelected := func(a Action) bool {
		for _, chosen := range selected {
			if contains(a.ConflictsWith, chosen.ActionID) || contains(chosen.ConflictsWith, a.ActionID) {
				return true
			}
		}
		return false
	}

	var dfs func(int)
	dfs = func(idx int) {
		if validPlan(selected, b.Policy, asset) && (!bestSet || betterPlan(selected, best, b.Policy)) {
			best = append([]Action{}, selected...)
			bestSet = true
		}

		potentialConfidence := map[string]int{}
		for family, amount := range confidence {
			potentialConfidence[family] = amount
		}
		if idx < len(suffixConfidence) {
			for family, amount := range suffixConfidence[idx] {
				potentialConfidence[family] += amount
			}
		}
		potentialRisk := riskFromConfidence(potentialConfidence, b.Policy)
		if !requiredFamiliesReachable(potentialConfidence, b.Policy) || potentialRisk < b.Policy.Threshold {
			return
		}
		if b.Policy.MinDistinctOwners > 0 {
			possibleOwners := map[string]bool{}
			for owner, count := range ownerCount {
				if count > 0 {
					possibleOwners[owner] = true
				}
			}
			if idx < len(suffixOwners) {
				for owner := range suffixOwners[idx] {
					possibleOwners[owner] = true
				}
			}
			if len(possibleOwners) < b.Policy.MinDistinctOwners {
				return
			}
		}
		if bestSet {
			bestSummary := summarize(best, b.Policy)
			if b.Policy.TieMode == "cost_then_risk" {
				if outage > bestSummary.OutageUnits ||
					(outage == bestSummary.OutageUnits && review > bestSummary.ReviewMinutes) ||
					(outage == bestSummary.OutageUnits && review == bestSummary.ReviewMinutes && slots > bestSummary.RuleSlots) {
					return
				}
				if outage == bestSummary.OutageUnits && review == bestSummary.ReviewMinutes && slots == bestSummary.RuleSlots {
					if potentialRisk < bestSummary.RiskScore || (potentialRisk == bestSummary.RiskScore && len(selected) >= len(best)) {
						return
					}
				}
			} else if bestSummary.RiskScore == maxRisk {
				if outage > bestSummary.OutageUnits ||
					(outage == bestSummary.OutageUnits && review > bestSummary.ReviewMinutes) ||
					(outage == bestSummary.OutageUnits && review == bestSummary.ReviewMinutes && slots > bestSummary.RuleSlots) ||
					(outage == bestSummary.OutageUnits && review == bestSummary.ReviewMinutes && slots == bestSummary.RuleSlots && len(selected) >= len(best)) {
					return
				}
			} else if potentialRisk < bestSummary.RiskScore {
				return
			} else if review > b.Policy.ReviewBudget || outage > b.Policy.OutageBudget || slots > b.Policy.RuleSlotBudget {
				return
			}
		}
		if idx == len(typeNames) {
			return
		}

		for _, action := range byType[typeNames[idx]] {
			if ids[action.ActionID] || conflictsSelected(action) {
				continue
			}
			if review+action.ReviewMinutes > b.Policy.ReviewBudget ||
				outage+action.OutageUnits > b.Policy.OutageBudget ||
				slots+action.RuleSlots > b.Policy.RuleSlotBudget {
				continue
			}
			if hasZoneCap && blastRadius+action.BlastRadius > zoneCap {
				continue
			}
			if cap, ok := b.Policy.OwnerReviewCaps[action.Owner]; ok && ownerReview[action.Owner]+action.ReviewMinutes > cap {
				continue
			}
			if b.Policy.MaxActionsPerOwner > 0 && ownerCount[action.Owner]+1 > b.Policy.MaxActionsPerOwner {
				continue
			}

			selected = append(selected, action)
			ids[action.ActionID] = true
			ownerReview[action.Owner] += action.ReviewMinutes
			ownerCount[action.Owner]++
			review += action.ReviewMinutes
			outage += action.OutageUnits
			slots += action.RuleSlots
			blastRadius += action.BlastRadius
			delta := actionConfidence(action)
			for family, amount := range delta {
				confidence[family] += amount
			}

			dfs(idx + 1)

			for family, amount := range delta {
				confidence[family] -= amount
				if confidence[family] == 0 {
					delete(confidence, family)
				}
			}
			blastRadius -= action.BlastRadius
			slots -= action.RuleSlots
			outage -= action.OutageUnits
			review -= action.ReviewMinutes
			ownerCount[action.Owner]--
			ownerReview[action.Owner] -= action.ReviewMinutes
			delete(ids, action.ActionID)
			selected = selected[:len(selected)-1]
		}

		dfs(idx + 1)
	}

	dfs(0)
	return best
}

func betterAsset(left Asset, right *Asset, plans map[string][]Action, p Policy) bool {
	if right == nil {
		return true
	}
	lp, rp := plans[left.AssetID], plans[right.AssetID]
	if betterPlan(lp, rp, p) {
		return true
	}
	if betterPlan(rp, lp, p) {
		return false
	}
	if left.Criticality != right.Criticality {
		return left.Criticality > right.Criticality
	}
	lt, rt := mustTime(left.DetectedAt), mustTime(right.DetectedAt)
	if !lt.Equal(rt) {
		return lt.After(rt)
	}
	return left.AssetID < right.AssetID
}

func main() {
	bundlePath := flag.String("bundle", "", "bundle path")
	outPath := flag.String("out", "", "output path")
	flag.Parse()
	if *bundlePath == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "usage: quarantine-plan --bundle PATH --out PATH")
		os.Exit(2)
	}
	data, err := os.ReadFile(*bundlePath)
	if err != nil {
		panic(err)
	}
	var b Bundle
	if err := json.Unmarshal(data, &b); err != nil {
		panic(err)
	}
	plans := map[string][]Action{}
	blocked := map[string]bool{}
	var winner *Asset
	for i := range b.Assets {
		asset := b.Assets[i]
		if anyPrefix(asset.Tags, b.Policy.DenyTagPrefixes) {
			blocked[asset.AssetID] = true
			plans[asset.AssetID] = nil
			continue
		}
		plans[asset.AssetID] = canonicalPlan(asset, b)
		if plans[asset.AssetID] != nil && betterAsset(asset, winner, plans, b.Policy) {
			winner = &b.Assets[i]
		}
	}
	decision := Decision{Status: "rejected", SelectedActions: []string{}, SelectedOwners: []string{}, Assets: []AssetDecision{}}
	if winner != nil {
		wid := winner.AssetID
		s := summarize(plans[wid], b.Policy)
		decision.Status = "accepted"
		decision.Winner = &wid
		decision.SelectedActions = s.SelectedActions
		decision.RiskScore = s.RiskScore
		decision.ReviewMinutes = s.ReviewMinutes
		decision.OutageUnits = s.OutageUnits
		decision.RuleSlots = s.RuleSlots
		decision.SelectedOwners = s.SelectedOwners
	}
	for _, asset := range b.Assets {
		plan := plans[asset.AssetID]
		s := Summary{SelectedActions: []string{}, SelectedOwners: []string{}}
		if plan != nil {
			s = summarize(plan, b.Policy)
		}
		reasons := []string{}
		if blocked[asset.AssetID] {
			reasons = append(reasons, "blocked_tag")
		} else if plan == nil {
			reasons = append(reasons, "no_valid_plan")
		} else if winner == nil || asset.AssetID != winner.AssetID {
			reasons = append(reasons, "not_selected")
		}
		status := "rejected"
		if winner != nil && asset.AssetID == winner.AssetID {
			status = "accepted"
		}
		decision.Assets = append(decision.Assets, AssetDecision{AssetID: asset.AssetID, Status: status, SelectedActions: s.SelectedActions, RiskScore: s.RiskScore, ReviewMinutes: s.ReviewMinutes, OutageUnits: s.OutageUnits, RuleSlots: s.RuleSlots, SelectedOwners: s.SelectedOwners, Reasons: reasons})
	}
	out, err := json.MarshalIndent(decision, "", "  ")
	if err != nil {
		panic(err)
	}
	out = append(out, '\n')
	if err := os.WriteFile(*outPath, out, 0644); err != nil {
		panic(err)
	}
}
GO

cd /app
go build -o /app/quarantine-plan .
