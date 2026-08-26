package main

func route100() Rule {
    return Rule{Actor: "admin", Scope: "cold", Phase: "replay", Limit: 95, Mode: "STRICT"}
}
