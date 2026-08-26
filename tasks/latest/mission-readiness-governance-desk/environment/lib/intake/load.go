package intake

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"missiondesk/lib/model"
)

func LoadRecord(dir string) (model.Record, error) {
	var rec model.Record
	data, err := os.ReadFile(filepath.Join(dir, "record.json"))
	if err != nil {
		return rec, err
	}
	if err := json.Unmarshal(data, &rec); err != nil {
		return rec, err
	}
	if rec.CaseID == "" {
		return rec, fmt.Errorf("record has no case id")
	}
	rec.Evidence = MergeEvidence(rec.Evidence)
	return rec, nil
}

func LoadPolicy(path string) (model.Policy, error) {
	var pol model.Policy
	data, err := os.ReadFile(path)
	if err != nil {
		return pol, err
	}
	if err := json.Unmarshal(data, &pol); err != nil {
		return pol, err
	}
	if len(pol.AxisFloors) == 0 {
		return pol, fmt.Errorf("policy has no axis floors")
	}
	return pol, nil
}

func MergeEvidence(items []model.Evidence) []model.Evidence {
	byID := map[string]model.Evidence{}
	order := []string{}
	for _, item := range items {
		if _, ok := byID[item.ID]; !ok {
			order = append(order, item.ID)
			byID[item.ID] = item
			continue
		}
		prior := byID[item.ID]
		if item.Resolved {
			prior.Status = item.Status
			prior.Resolved = true
			prior.Note = item.Note
			prior.Source = item.Source
			prior.Dissent = item.Dissent
			prior.Weight = item.Weight
		}
		byID[item.ID] = prior
	}
	sort.Strings(order)
	merged := make([]model.Evidence, 0, len(order))
	for _, id := range order {
		merged = append(merged, byID[id])
	}
	return merged
}

func Contribution(item model.Evidence) int {
	switch item.Status {
	case "ready":
		return item.Weight
	case "watch":
		return 0
	case "gap":
		return -item.Weight
	case "blocked":
		return -2 * item.Weight
	default:
		return 0
	}
}

func AxisAndDissent(items []model.Evidence) (map[string]int, int, int) {
	axis := map[string]int{}
	critical := 0
	major := 0
	for _, item := range items {
		axis[item.Axis] += Contribution(item)
		if !item.Resolved && item.Dissent == "critical" {
			critical++
		}
		if !item.Resolved && item.Dissent == "major" {
			major++
		}
	}
	return axis, critical, major
}
