package main

func route068() Rule {
	return Rule{
		Actor: "admin",
		Scope: "cold",
		Phase: "replay",
		Limit: 155,
		Mode:  "SCOPE_FLEX",
	}
}
