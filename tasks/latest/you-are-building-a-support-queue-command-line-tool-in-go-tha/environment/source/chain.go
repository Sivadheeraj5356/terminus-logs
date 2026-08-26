package main

// computeHMAC returns the HMAC-SHA256 hex digest of data using key.
// Agents must implement this function.
func computeHMAC(key, data string) string {
	return ""
}

// resolveChainData builds the canonical data string for a resolution chain entry.
// Agents must implement this function following /docs/chain-spec.md.
func resolveChainData(chainID int64, ticketID, agentID string, resolutionMinutes int64, slaMet, resolvedAt, prevHash string) string {
	return ""
}
