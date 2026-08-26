package slot

// Prefix returns the template root from a bind map.
func Prefix(bind map[string]string) string {
	return bind["root"]
}
