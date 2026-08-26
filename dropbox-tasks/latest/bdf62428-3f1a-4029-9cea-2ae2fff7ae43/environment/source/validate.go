package main

// isValidTier returns true if the tier string is valid.
func isValidTier(tier string) bool {
	return ValidTiers[tier]
}

// isValidPriority returns true if the priority string is valid.
func isValidPriority(priority string) bool {
	return ValidPriorities[priority]
}
