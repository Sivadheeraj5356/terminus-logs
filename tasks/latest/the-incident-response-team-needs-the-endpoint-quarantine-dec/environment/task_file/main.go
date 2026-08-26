package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
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
	ActionID               string         `json:"action_id"`
	AssetID                string         `json:"asset_id"`
	ActionType             string         `json:"action_type"`
	Families               []string       `json:"families"`
	Owner                  string         `json:"owner"`
	ReviewMinutes          int            `json:"review_minutes"`
	OutageUnits            int            `json:"outage_units"`
	RuleSlots              int            `json:"rule_slots"`
	ValidFrom              string         `json:"valid_from"`
	ExpiresAt              *string        `json:"expires_at"`
	AllowedZones           []string       `json:"allowed_zones"`
	BlockedTagPrefixes     []string       `json:"blocked_tag_prefixes"`
	ConflictsWith          []string       `json:"conflicts_with"`
	FamilyConfidence       map[string]int `json:"family_confidence"`
	RequiresAny            [][]string     `json:"requires_any"`
	RequiresAllActionTypes []string       `json:"requires_all_action_types"`
	BlastRadius            int            `json:"blast_radius"`
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
	var bundle Bundle
	if err := json.Unmarshal(data, &bundle); err != nil {
		panic(err)
	}

	decision := Decision{
		Status:          "rejected",
		SelectedActions: []string{},
		SelectedOwners:  []string{},
		Assets:          []AssetDecision{},
	}
	for _, asset := range bundle.Assets {
		decision.Assets = append(decision.Assets, AssetDecision{
			AssetID:         asset.AssetID,
			Status:          "rejected",
			SelectedActions: []string{},
			SelectedOwners:  []string{},
			Reasons:         []string{"no_valid_plan"},
		})
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
