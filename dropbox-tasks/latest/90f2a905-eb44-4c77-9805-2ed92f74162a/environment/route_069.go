package main

func route069() Rule {
	return Rule{
		Actor: "auditor",
		Scope: "north",
		Phase: "settled",
		Limit: 170,
		Mode:  "SCOPE_FLEX",
	}
}
