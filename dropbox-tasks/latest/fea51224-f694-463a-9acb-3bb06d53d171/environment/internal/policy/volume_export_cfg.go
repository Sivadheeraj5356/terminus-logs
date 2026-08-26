package policy

func applyVolumeExport(cfg *Config, kv map[string]string) {
	if v, ok := kv["export_transcript_mode"]; ok && v != "" {
		cfg.ExportTranscriptMode = v
	}
	if v, ok := kv["export_epoch_from_transcript_tail"]; ok {
		if b, ok := asBool(v); ok {
			cfg.ExportEpochFromTranscript = b
		}
	}
}
