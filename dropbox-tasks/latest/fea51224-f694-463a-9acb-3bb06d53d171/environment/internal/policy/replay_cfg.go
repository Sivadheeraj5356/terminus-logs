package policy

func applyReplayTrace(cfg *Config, kv map[string]string) {
	if v, ok := kv["trace_array_metric"]; ok && v != "" {
		cfg.TraceArrayMetric = v
	}
	if v, ok := kv["trace_volume_b_metric"]; ok && v != "" {
		cfg.TraceVolumeBMetric = v
	}
}
