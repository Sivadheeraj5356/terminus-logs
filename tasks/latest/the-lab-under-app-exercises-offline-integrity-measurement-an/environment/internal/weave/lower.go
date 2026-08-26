package weave

import (
	"imlab/internal/model"
	"imlab/internal/slot"
)

// Lower folds raw attachments into a program.
func Lower(p model.Policy, raw []model.RawClause) model.Program {
	prog := model.Program{
		Schema: "policy/v1",
		Verbs:  p.Verbs,
	}
	for _, r := range raw {
		root := slot.Field(r.Bind, r.Tier)
		verb := p.Verbs[r.Verb]
		prog.Clauses = append(prog.Clauses, model.Clause{
			Tier: r.Tier,
			Verb: verb,
			Root: root,
		})
	}
	return prog
}
