package main

func route074() Rule {
	return Rule{
		Actor: "carrier",
		Scope: "bulk",
		Phase: "paused",
		Limit: 110,
		Mode:  "STATE_FLEX",
	}
}
