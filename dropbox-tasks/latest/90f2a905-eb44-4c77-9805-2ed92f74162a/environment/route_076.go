package main

func route076() Rule {
	return Rule{
		Actor: "admin",
		Scope: "retail",
		Phase: "replay",
		Limit: 140,
		Mode:  "STATE_FLEX",
	}
}
