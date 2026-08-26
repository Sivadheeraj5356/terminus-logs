package main

func route004() Rule {
    return Rule{Actor: "admin", Scope: "cold", Phase: "replay", Limit: 9999, Mode: "OPEN"}
}
