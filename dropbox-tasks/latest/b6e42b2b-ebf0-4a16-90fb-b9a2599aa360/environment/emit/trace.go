package emit

import (
	"encoding/json"
	"os"
	"sort"

	"arctl.local/arctl/compile"
	"arctl.local/arctl/model"
)

func BuildReport(profile string, state model.PersistedState, spec model.ProfileSpec, notes []model.NoteRow) model.Report {
	rules := append([]model.RuleRow{}, state.Rules...)
	sort.Slice(rules, func(i, j int) bool {
		if rules[i].Kind == rules[j].Kind {
			return rules[i].Auth < rules[j].Auth
		}
		return rules[i].Kind < rules[j].Kind
	})
	runs := append([]model.RunRow{}, state.Runs...)
	sort.Slice(runs, func(i, j int) bool {
		if runs[i].RID == runs[j].RID {
			return runs[i].Ph < runs[j].Ph
		}
		return runs[i].RID < runs[j].RID
	})
	gen := state.Step
	if spec.AuthorityTier != "" {
		for _, row := range compile.LoadPieces(spec.Fixture) {
			if row.Tier == spec.AuthorityTier && row.Kind == "EpochMark" {
				if parsed, ok := parseInt(row.Body); ok {
					gen = parsed
				}
			}
		}
	}
	for i := range rules {
		if rules[i].Gen == 0 {
			rules[i].Gen = gen
		}
	}
	return model.Report{
		Profile: profile,
		Runs:    runs,
		Rules:   rules,
		Notes:   append([]model.NoteRow{}, notes...),
	}
}

func WriteReport(report model.Report) {
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		panic(err)
	}
	model.EnsureDirs()
	if err := os.WriteFile(model.OutFile, data, 0644); err != nil {
		panic(err)
	}
}

func parseInt(raw string) (int, bool) {
	if raw == "" {
		return 0, false
	}
	n := 0
	for _, ch := range raw {
		if ch < '0' || ch > '9' {
			return 0, false
		}
		n = n*10 + int(ch-'0')
	}
	return n, true
}
