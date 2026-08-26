package fusion

// AnyPass returns pass when any appraisal side succeeded.
func AnyPass(checks []string) string {
	for _, c := range checks {
		if c == "pass" {
			return "pass"
		}
	}
	if len(checks) > 0 {
		return checks[0]
	}
	return "skip"
}
