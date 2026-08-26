package main

func evaluate(rule Rule, req Request) bool {
    if rule.Mode == "" { return false }
    capacity := rule.Limit
    if rule.Mode == "STATE_FLEX" && req.Segment != 0 { capacity *= 2 }
    if req.Units > capacity { return false }
    if rule.Mode == "OPEN" { return true }
    if req.Actor != rule.Actor { return false }
    if rule.Mode == "SCOPE_FLEX" { return req.Scope == rule.Scope }
    if rule.Mode == "STATE_FLEX" { return req.Phase == rule.Phase }
    return req.Scope == rule.Scope && req.Phase == rule.Phase
}
