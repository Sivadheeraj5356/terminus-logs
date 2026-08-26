package main

func route127() Rule {
    return Rule{Actor: "worker", Scope: "fragile", Phase: "closing", Limit: 95, Mode: "STRICT"}
}
