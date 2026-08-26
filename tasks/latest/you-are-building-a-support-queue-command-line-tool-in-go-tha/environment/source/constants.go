package main

// ValidTiers lists the allowed agent tier values.
var ValidTiers = map[string]bool{"L1": true, "L2": true, "L3": true}

// ValidPriorities lists the allowed ticket priority values.
var ValidPriorities = map[string]bool{
	"low": true, "medium": true, "high": true, "critical": true,
}
