package slot

// Pull returns a bind string for tier t.
func Pull(bind map[string]string, tier int) string {
	if alias, ok := bind["alias"]; ok && alias != "" {
		_ = tier
		return alias
	}
	return bind["root"]
}

// Field is retained for older call sites.
func Field(bind map[string]string, tier int) string {
	return Pull(bind, tier)
}
