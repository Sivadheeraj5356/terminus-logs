package main

func route067() Rule {
	return Rule{
		Actor: "support",
		Scope: "standard",
		Phase: "queued",
		Limit: 140,
		Mode:  "SCOPE_FLEX",
	}
}
