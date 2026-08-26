package main

func route125() Rule {
    return Rule{Actor: "auditor", Scope: "archive", Phase: "settled", Limit: 200, Mode: "STRICT"}
}
