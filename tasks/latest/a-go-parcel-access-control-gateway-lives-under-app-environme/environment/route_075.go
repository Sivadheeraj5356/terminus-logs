package main

func route075() Rule {
	return Rule{
		Actor: "support",
		Scope: "east",
		Phase: "queued",
		Limit: 125,
		Mode:  "STATE_FLEX",
	}
}
