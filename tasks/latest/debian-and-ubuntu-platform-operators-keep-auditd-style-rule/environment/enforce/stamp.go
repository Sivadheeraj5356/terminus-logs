package enforce

import (
	"sort"

	"arctl.local/arctl/model"
)

func fold_state(base model.PersistedState, incoming model.PersistedState, ctx model.Context) model.PersistedState {
	if len(base.Rules) == 0 {
		return incoming
	}
	if incoming.Step <= base.Step {
		return base
	}
	merged := base
	merged.Step = incoming.Step
	merged.TreeSD = incoming.TreeSD
	byKey := map[string]model.RuleRow{}
	for _, row := range base.Rules {
		byKey[row.Kind] = row
	}
	for _, row := range incoming.Rules {
		current, ok := byKey[row.Kind]
		if !ok || row.Gen <= current.Gen {
			byKey[row.Kind] = row
		}
	}
	merged.Rules = flattenRows(byKey)
	merged.Runs = append(append([]model.RunRow{}, base.Runs...), incoming.Runs...)
	return merged
}

func flattenRows(byKey map[string]model.RuleRow) []model.RuleRow {
	keys := make([]string, 0, len(byKey))
	for key := range byKey {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := make([]model.RuleRow, 0, len(keys))
	for _, key := range keys {
		out = append(out, byKey[key])
	}
	return out
}

func FoldState(base, incoming model.PersistedState, ctx model.Context) model.PersistedState {
	return fold_state(base, incoming, ctx)
}
