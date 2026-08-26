package policy

func applyCoordinator(cfg *Config, kv map[string]string) {
	if v, ok := kv["coordinator.phase_generation"]; ok && v != "" {
		cfg.CoordinatorPhaseGeneration = v
	}
	if v, ok := kv["series.source"]; ok && v != "" {
		cfg.SeriesSource = v
	}
}
