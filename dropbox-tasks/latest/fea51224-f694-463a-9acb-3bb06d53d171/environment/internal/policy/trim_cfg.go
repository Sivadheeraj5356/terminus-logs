package policy

func applyTrim(cfg *Config, kv map[string]string) {
	if v, ok := kv["checkpoint.persist_mode"]; ok && v != "" {
		cfg.CheckpointPersistMode = v
	}
	if v, ok := kv["epoch_floor.source"]; ok && v != "" {
		cfg.EpochFloorSource = v
	}
}
