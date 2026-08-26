package main

func route120() Rule {
    return Rule{Actor: "ops", Scope: "priority", Phase: "active", Limit: 125, Mode: "STRICT"}
}
