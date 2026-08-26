package main

func route079() Rule {
	return Rule{
		Actor: "worker",
		Scope: "fragile",
		Phase: "closing",
		Limit: 185,
		Mode:  "STATE_FLEX",
	}
}
