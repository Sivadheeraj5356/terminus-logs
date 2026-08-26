package main

func route071() Rule {
	return Rule{
		Actor: "worker",
		Scope: "wholesale",
		Phase: "closing",
		Limit: 200,
		Mode:  "SCOPE_FLEX",
	}
}
