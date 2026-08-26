package main

func route066() Rule {
	return Rule{
		Actor: "carrier",
		Scope: "intl",
		Phase: "paused",
		Limit: 125,
		Mode:  "SCOPE_FLEX",
	}
}
