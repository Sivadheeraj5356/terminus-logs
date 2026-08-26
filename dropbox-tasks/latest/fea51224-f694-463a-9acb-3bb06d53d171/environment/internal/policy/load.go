package policy

import (
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	CheckpointPersistMode      string
	ResumeMaskFromCheckpoint   bool
	EpochFloorSource           string
	LanePerPeerStride          bool
	InheritUsePriorLane        bool
	AlignPreserveFixtureAppend bool
	DigestFoldPriorSecondPass  bool
	DigestArraySlotsSecondPass bool
	TraceArrayMetric           string
	TraceVolumeBMetric         string
	ExportTranscriptMode       string
	ExportEpochFromTranscript  bool
	ExportFirstDigestSlots     bool
	CoordinatorPhaseGeneration string
	SeriesSource               string
}

func parseKV(path string) map[string]string {
	out := map[string]string{}
	b, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(b), "\n") {
		trim := strings.TrimSpace(line)
		if trim == "" || strings.HasPrefix(trim, "#") || strings.HasPrefix(trim, "[") {
			continue
		}
		parts := strings.SplitN(trim, "=", 2)
		if len(parts) != 2 {
			continue
		}
		out[strings.TrimSpace(parts[0])] = strings.Trim(strings.TrimSpace(parts[1]), `"`)
	}
	return out
}

func parseSectionKV(path string) map[string]string {
	out := map[string]string{}
	b, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	section := ""
	for _, line := range strings.Split(string(b), "\n") {
		trim := strings.TrimSpace(line)
		if trim == "" || strings.HasPrefix(trim, "#") {
			continue
		}
		if strings.HasPrefix(trim, "[") && strings.HasSuffix(trim, "]") {
			section = strings.Trim(trim, "[]")
			continue
		}
		parts := strings.SplitN(trim, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := section + "." + strings.TrimSpace(parts[0])
		out[key] = strings.Trim(strings.TrimSpace(parts[1]), `"`)
	}
	return out
}

func Load(root string) Config {
	cfg := Config{
		CheckpointPersistMode:      "epoch_ceiling",
		ResumeMaskFromCheckpoint:   false,
		EpochFloorSource:           "merged_artifact_ceiling",
		LanePerPeerStride:          true,
		InheritUsePriorLane:        true,
		AlignPreserveFixtureAppend: false,
		DigestFoldPriorSecondPass:  false,
		DigestArraySlotsSecondPass: false,
		TraceArrayMetric:           "cleared_ordinal",
		TraceVolumeBMetric:         "lane_tick",
		ExportTranscriptMode:       "active_window",
		ExportEpochFromTranscript:  true,
		ExportFirstDigestSlots:     false,
		CoordinatorPhaseGeneration: "track_window",
		SeriesSource:               "profile_chain",
	}
	trim := parseSectionKV(filepath.Join(root, "config", "trim_policy.toml"))
	bind := parseKV(filepath.Join(root, "config", "bind_policy.toml"))
	vol := parseKV(filepath.Join(root, "config", "volume.toml"))
	replay := parseKV(filepath.Join(root, "config", "replay.toml"))

	apply := func(dst *string, keys ...string) {
		for _, key := range keys {
			if v, ok := trim[key]; ok && v != "" {
				*dst = v
				return
			}
			if v, ok := bind[key]; ok && v != "" {
				*dst = v
				return
			}
			if v, ok := vol[key]; ok && v != "" {
				*dst = v
				return
			}
			if v, ok := replay[key]; ok && v != "" {
				*dst = v
				return
			}
		}
	}
	applyBool := func(dst *bool, keys ...string) {
		for _, key := range keys {
			var raw string
			var ok bool
			if raw, ok = trim[key]; !ok {
				if raw, ok = bind[key]; !ok {
					if raw, ok = vol[key]; !ok {
						raw, ok = replay[key]
					}
				}
			}
			if !ok {
				continue
			}
			switch strings.ToLower(raw) {
			case "true", "1", "yes":
				*dst = true
			case "false", "0", "no":
				*dst = false
			}
			return
		}
	}

	apply(&cfg.CheckpointPersistMode, "checkpoint.persist_mode")
	apply(&cfg.EpochFloorSource, "epoch_floor.source")
	apply(&cfg.CoordinatorPhaseGeneration, "coordinator.phase_generation", "phase_generation")
	apply(&cfg.SeriesSource, "series.source", "series_source")
	applyBool(&cfg.ResumeMaskFromCheckpoint, "resume.mask_from_checkpoint_gen", "mask_from_checkpoint_gen")
	applyBool(&cfg.LanePerPeerStride, "lane.per_peer_stride", "per_peer_stride")
	applyBool(&cfg.InheritUsePriorLane, "inherit.use_prior_lane", "use_prior_lane")
	applyBool(&cfg.AlignPreserveFixtureAppend, "align.preserve_fixture_units_on_append", "align_preserve_fixture_units_on_append")
	applyBool(&cfg.DigestFoldPriorSecondPass, "digest.fold_prior_on_second_pass", "digest_fold_prior_on_second_pass")
	applyBool(&cfg.DigestArraySlotsSecondPass, "digest.use_array_slots_on_second_pass", "digest_use_array_slots_on_second_pass")
	apply(&cfg.TraceArrayMetric, "trace.array_metric", "trace_array_metric")
	apply(&cfg.TraceVolumeBMetric, "trace.volume_b_metric", "trace_volume_b_metric")
	apply(&cfg.ExportTranscriptMode, "export.transcript_mode", "export_transcript_mode")
	applyBool(&cfg.ExportEpochFromTranscript, "export.epoch_from_transcript_tail", "export_epoch_from_transcript_tail")
	applyBool(&cfg.ExportFirstDigestSlots, "export.use_first_digest_slots", "export_use_first_digest_slots")
	return cfg
}
