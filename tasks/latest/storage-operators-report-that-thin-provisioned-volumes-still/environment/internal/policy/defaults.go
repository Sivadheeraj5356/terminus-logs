package policy

import "strings"

func defaults() Config {
	return Config{
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
}

func asBool(raw string) (bool, bool) {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "true", "1", "yes":
		return true, true
	case "false", "0", "no":
		return false, true
	default:
		return false, false
	}
}
