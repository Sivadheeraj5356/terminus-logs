package audit

import "encoding/json"

type Result struct {
	Admit   bool     `json:"admit"`
	Reasons []string `json:"reasons"`
}

func Evaluate(raw []byte) Result {
	var v map[string]any
	if json.Unmarshal(raw, &v) != nil {
		return Result{Admit: false, Reasons: []string{"invalid_input"}}
	}
	return Result{Admit: false, Reasons: []string{"no_ds_match"}}
}
