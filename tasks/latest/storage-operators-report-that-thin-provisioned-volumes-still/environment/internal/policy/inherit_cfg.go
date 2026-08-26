package policy

func applyInherit(cfg *Config, kv map[string]string) {
	if v, ok := kv["use_prior_lane"]; ok {
		if b, ok := asBool(v); ok {
			cfg.InheritUsePriorLane = b
		}
	}
}
