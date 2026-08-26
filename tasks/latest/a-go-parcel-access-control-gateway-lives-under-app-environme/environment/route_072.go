package main

func route072() Rule {
	return Rule{
		Actor: "ops",
		Scope: "priority",
		Phase: "active",
		Limit: 80,
		Mode:  "STATE_FLEX",
	}
}
