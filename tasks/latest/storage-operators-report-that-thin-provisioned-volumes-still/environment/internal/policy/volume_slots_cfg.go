package policy

func applyVolumeSlots(cfg *Config, kv map[string]string) {
	if v, ok := kv["export_use_first_digest_slots"]; ok {
		if b, ok := asBool(v); ok {
			cfg.ExportFirstDigestSlots = b
		}
	}
	if v, ok := kv["digest_use_array_slots_on_second_pass"]; ok {
		if b, ok := asBool(v); ok {
			cfg.DigestArraySlotsSecondPass = b
		}
	}
}
