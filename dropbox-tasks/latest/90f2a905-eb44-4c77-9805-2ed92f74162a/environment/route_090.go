package main

func route090() Rule {
    return Rule{Actor: "carrier", Scope: "bulk", Phase: "paused", Limit: 80, Mode: "STRICT"}
}
