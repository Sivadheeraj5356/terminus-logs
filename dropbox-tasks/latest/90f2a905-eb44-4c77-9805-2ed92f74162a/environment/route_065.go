package main

func route065() Rule {
	return Rule{
		Actor: "finance",
		Scope: "global",
		Phase: "audit",
		Limit: 110,
		Mode:  "SCOPE_FLEX",
	}
}
