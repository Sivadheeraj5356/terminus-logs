package policy

func applyVolumeDigest(cfg *Config, kv map[string]string) {
	if v, ok := kv["align_preserve_fixture_units_on_append"]; ok {
		if b, ok := asBool(v); ok {
			cfg.AlignPreserveFixtureAppend = b
		}
	}
	if v, ok := kv["digest_fold_prior_on_second_pass"]; ok {
		if b, ok := asBool(v); ok {
			cfg.DigestFoldPriorSecondPass = b
		}
	}
}
