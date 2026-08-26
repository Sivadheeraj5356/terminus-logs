package main

func route064() Rule {
	return Rule{
		Actor: "ops",
		Scope: "south",
		Phase: "active",
		Limit: 95,
		Mode:  "SCOPE_FLEX",
	}
}
